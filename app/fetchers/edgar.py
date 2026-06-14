"""
app/fetchers/edgar.py
SEC EDGAR fetcher — polls for 13D/13G/8-K filings on watched companies.

Free API, no auth required. SEC requires a User-Agent header identifying you.
Rate limit: 10 requests/second.

Key endpoints used:
  EFTS full-text search: https://efts.sec.gov/LATEST/search-index
  Submissions per CIK:   https://data.sec.gov/submissions/CIK{padded_cik}.json
  Company search:        https://company_search not used — we use CIK lookup

Pipeline:
  fetch_recent_filings(form_types, since_date)
    → for each filing: compute content_hash
    → Level 1 dedup: skip if hash already in raw_ingestions
    → write raw_ingestions row (extraction_status = "pending")
    → enqueue job_queue row (job_type = "ingest_source")
    → return FetchResult summary

Usage:
  # Standalone (no DB) — for testing:
  python -m app.fetchers.edgar

  # With DB:
  DATABASE_URL="postgresql://..." python -m app.fetchers.edgar
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_FILING_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/"
    "{accession_nodash}-index.htm"
)

# SEC requires a descriptive User-Agent: "Company Name contact@email.com"
USER_AGENT = "MeetMagus Intelligence meetmagus@tidalpartners.com"

# 10 req/sec hard limit from SEC. We stay at 8 to be safe.
MAX_REQUESTS_PER_SECOND = 8
MIN_INTERVAL_SECONDS = 1.0 / MAX_REQUESTS_PER_SECOND

# Form types we care about
FORM_TYPES_ACTIVIST = ["SC 13D", "SC 13D/A"]  # activist / large stake
FORM_TYPES_PASSIVE = ["SC 13G", "SC 13G/A"]   # passive large stake
FORM_TYPES_MATERIAL = ["8-K", "8-K/A"]         # material events
FORM_TYPES_INSIDER = ["4"]                      # insider transactions
FORM_TYPES_DEFAULT = FORM_TYPES_ACTIVIST + FORM_TYPES_PASSIVE + FORM_TYPES_MATERIAL

# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class EdgarFiling:
    """A single filing returned from EDGAR EFTS search."""
    accession_no: str          # e.g. "0000950170-26-012345"
    form_type: str             # e.g. "SC 13D"
    filed_at: date             # filing date
    company_name: str          # subject company name (as reported by SEC)
    company_cik: str           # subject company CIK (zero-padded 10 digits)
    filer_name: str            # who filed (the activist / institution)
    filer_cik: str             # filer CIK
    document_url: str          # URL to primary document
    raw_text: str              # full text of the primary document (or excerpt)
    content_hash: str          # SHA-256 of raw_text
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_efts_hit(cls, hit: dict) -> "EdgarFiling":
        """Build an EdgarFiling from one EFTS search result hit."""
        src = hit.get("_source", {})
        accession = src.get("file_num", "") or hit.get("_id", "")
        # EFTS uses period-separated accession in _id: "0001234567-26-000001"
        accession_no = hit.get("_id", "").replace(":", "-")

        filed_str = src.get("period_of_report") or src.get("file_date") or ""
        try:
            filed_at = date.fromisoformat(filed_str[:10])
        except (ValueError, TypeError):
            filed_at = date.today()

        # entity_name is the subject company; display_names[0] is the filer
        entity_name = src.get("entity_name", "")
        display_names = src.get("display_names", [])
        filer_name = display_names[0] if display_names else ""

        # CIKs
        company_cik = str(src.get("entity_id", "")).zfill(10)
        filer_ciks = src.get("file_num", "")  # not always available

        # Build document URL from accession
        accession_nodash = accession_no.replace("-", "")
        cik_raw = src.get("entity_id", "0")
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_raw}/"
            f"{accession_nodash}/{accession_nodash}-index.htm"
        )

        raw_text = json.dumps(src, indent=2)
        content_hash = hashlib.sha256(raw_text.encode()).hexdigest()

        return cls(
            accession_no=accession_no,
            form_type=src.get("form_type", ""),
            filed_at=filed_at,
            company_name=entity_name,
            company_cik=company_cik,
            filer_name=filer_name,
            filer_cik="",
            document_url=doc_url,
            raw_text=raw_text,
            content_hash=content_hash,
            metadata=src,
        )


@dataclass
class FetchResult:
    """Summary of one fetch run."""
    form_types: list[str]
    since_date: date
    total_found: int = 0
    new_ingestions: int = 0       # rows written to raw_ingestions
    skipped_dedup: int = 0        # Level 1 hash duplicates skipped
    errors: list[str] = field(default_factory=list)
    filings: list[EdgarFiling] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Rate limiter
# ──────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple token-bucket rate limiter for EDGAR's 10 req/sec limit."""

    def __init__(self, max_per_second: float = MAX_REQUESTS_PER_SECOND):
        self.min_interval = 1.0 / max_per_second
        self._last_call: float = 0.0

    def wait(self) -> None:
        """Block until it's safe to make another request."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


# ──────────────────────────────────────────────────────────────────────────────
# EDGAR client
# ──────────────────────────────────────────────────────────────────────────────

class EdgarClient:
    """Thin HTTP client for SEC EDGAR APIs."""

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
            timeout=timeout,
            follow_redirects=True,
            trust_env=False,  # ignore system proxy settings
        )
        self._limiter = RateLimiter()

    def _get(self, url: str, params: dict | None = None) -> dict:
        self._limiter.wait()
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def search_filings(
        self,
        form_types: list[str],
        since_date: date,
        until_date: date | None = None,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Search EDGAR EFTS for filings of given form types in a date range.
        Returns raw EFTS hits (list of dicts).
        """
        until = until_date or date.today()
        forms_param = ",".join(form_types)

        all_hits: list[dict] = []
        from_offset = 0
        page_size = min(max_results, 100)

        while from_offset < max_results:
            params = {
                "forms": forms_param,
                "dateRange": "custom",
                "startdt": since_date.isoformat(),
                "enddt": until.isoformat(),
                "from": from_offset,
                "hits.hits.total.value": page_size,
                "_source": "true",
            }
            try:
                data = self._get(EDGAR_EFTS_URL, params=params)
            except httpx.HTTPStatusError as e:
                logger.error("EDGAR EFTS error: %s", e)
                break

            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            all_hits.extend(hits)
            from_offset += len(hits)

            total_available = (
                data.get("hits", {}).get("total", {}).get("value", 0)
            )
            if from_offset >= total_available:
                break

        return all_hits

    def get_company_submissions(self, cik: str) -> dict:
        """
        Fetch all submissions for a company by CIK.
        Returns the raw submissions JSON.
        """
        padded = str(cik).lstrip("0").zfill(10)
        url = EDGAR_SUBMISSIONS_URL.format(cik=padded)
        return self._get(url)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# Fetcher — orchestrates client + DB writes
# ──────────────────────────────────────────────────────────────────────────────

class EdgarFetcher:
    """
    High-level fetcher. Polls EDGAR and optionally persists to DB.

    Usage without DB (dry run / testing):
        fetcher = EdgarFetcher(db_session=None)
        result = fetcher.fetch_recent_filings(["SC 13D"], since_days=7)

    Usage with DB:
        from sqlalchemy.orm import Session
        fetcher = EdgarFetcher(db_session=session)
        result = fetcher.fetch_recent_filings(["SC 13D", "SC 13G"], since_days=1)
    """

    def __init__(self, db_session=None):
        self._client = EdgarClient()
        self._db = db_session

    def fetch_recent_filings(
        self,
        form_types: list[str] | None = None,
        since_days: int = 1,
        since_date: date | None = None,
        max_results: int = 100,
    ) -> FetchResult:
        """
        Fetch filings filed in the last `since_days` days (or since `since_date`).
        Deduplicates at Level 1 (content hash). Writes to DB if session provided.
        """
        forms = form_types or FORM_TYPES_DEFAULT
        start = since_date or (date.today() - timedelta(days=since_days))

        result = FetchResult(form_types=forms, since_date=start)

        logger.info(
            "Fetching %s filings since %s", forms, start.isoformat()
        )

        hits = self._client.search_filings(forms, start, max_results=max_results)
        result.total_found = len(hits)

        for hit in hits:
            try:
                filing = EdgarFiling.from_efts_hit(hit)
            except Exception as e:
                result.errors.append(f"Parse error for hit {hit.get('_id')}: {e}")
                continue

            # Level 1 dedup: content hash
            if self._db and self._is_duplicate(filing.content_hash):
                result.skipped_dedup += 1
                logger.debug("Skipping duplicate: %s", filing.accession_no)
                continue

            result.filings.append(filing)

            if self._db:
                try:
                    self._write_raw_ingestion(filing)
                    self._enqueue_extraction(filing)
                    result.new_ingestions += 1
                except Exception as e:
                    result.errors.append(
                        f"DB write error for {filing.accession_no}: {e}"
                    )
            else:
                # Dry run — count as new
                result.new_ingestions += 1

        logger.info(
            "Fetch complete: %d found, %d new, %d deduped, %d errors",
            result.total_found,
            result.new_ingestions,
            result.skipped_dedup,
            len(result.errors),
        )
        return result

    def fetch_for_company(
        self,
        cik: str,
        form_types: list[str] | None = None,
        since_days: int = 30,
    ) -> FetchResult:
        """
        Fetch recent filings for a specific company CIK.
        Uses the EDGAR submissions endpoint for targeted lookup.
        """
        forms = form_types or FORM_TYPES_DEFAULT
        start = date.today() - timedelta(days=since_days)

        result = FetchResult(form_types=forms, since_date=start)

        try:
            data = self._client.get_company_submissions(cik)
        except Exception as e:
            result.errors.append(f"Submissions fetch error for CIK {cik}: {e}")
            return result

        recent = data.get("filings", {}).get("recent", {})
        form_col = recent.get("form", [])
        date_col = recent.get("filingDate", [])
        accession_col = recent.get("accessionNumber", [])
        entity_name = data.get("name", "")

        for i, form in enumerate(form_col):
            if form not in forms:
                continue
            try:
                filed = date.fromisoformat(date_col[i])
            except (ValueError, IndexError):
                continue
            if filed < start:
                continue

            accession = accession_col[i] if i < len(accession_col) else ""
            accession_nodash = accession.replace("-", "")

            raw_payload = {
                "form_type": form,
                "filed_at": date_col[i],
                "entity_name": entity_name,
                "entity_cik": cik,
                "accession_no": accession,
                "document_url": (
                    f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/"
                    f"{accession_nodash}/{accession_nodash}-index.htm"
                ),
            }
            raw_text = json.dumps(raw_payload)
            content_hash = hashlib.sha256(raw_text.encode()).hexdigest()

            filing = EdgarFiling(
                accession_no=accession,
                form_type=form,
                filed_at=filed,
                company_name=entity_name,
                company_cik=str(cik).zfill(10),
                filer_name="",
                filer_cik="",
                document_url=raw_payload["document_url"],
                raw_text=raw_text,
                content_hash=content_hash,
                metadata=raw_payload,
            )

            result.total_found += 1

            if self._db and self._is_duplicate(content_hash):
                result.skipped_dedup += 1
                continue

            result.filings.append(filing)
            if self._db:
                try:
                    self._write_raw_ingestion(filing)
                    self._enqueue_extraction(filing)
                    result.new_ingestions += 1
                except Exception as e:
                    result.errors.append(
                        f"DB write error for {accession}: {e}"
                    )
            else:
                result.new_ingestions += 1

        return result

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _is_duplicate(self, content_hash: str) -> bool:
        """Level 1 dedup: check if content_hash already exists in raw_ingestions."""
        if not self._db:
            return False
        from sqlalchemy import text
        row = self._db.execute(
            text(
                "SELECT 1 FROM platform.raw_ingestions "
                "WHERE content_hash = :h LIMIT 1"
            ),
            {"h": content_hash},
        ).fetchone()
        return row is not None

    def _write_raw_ingestion(self, filing: EdgarFiling) -> str:
        """Insert a row into platform.raw_ingestions. Returns the new UUID."""
        from sqlalchemy import text
        result = self._db.execute(
            text("""
                INSERT INTO platform.raw_ingestions
                    (source_id, content_hash, raw_content, content_type,
                     extraction_status, metadata, fetched_at)
                VALUES
                    ('edgar', :hash, :content, 'application/json',
                     'pending', :meta::jsonb, NOW())
                ON CONFLICT (content_hash) DO NOTHING
                RETURNING id
            """),
            {
                "hash": filing.content_hash,
                "content": filing.raw_text,
                "meta": json.dumps({
                    "form_type": filing.form_type,
                    "accession_no": filing.accession_no,
                    "company_name": filing.company_name,
                    "company_cik": filing.company_cik,
                    "filer_name": filing.filer_name,
                    "filed_at": filing.filed_at.isoformat(),
                    "document_url": filing.document_url,
                }),
            },
        )
        self._db.commit()
        row = result.fetchone()
        return str(row[0]) if row else ""

    def _enqueue_extraction(self, filing: EdgarFiling) -> None:
        """Add an extraction job to platform.job_queue."""
        from sqlalchemy import text
        self._db.execute(
            text("""
                INSERT INTO platform.job_queue
                    (job_type, priority, payload, status, attempts)
                VALUES
                    ('ingest_source', 2, :payload::jsonb, 'pending', 0)
            """),
            {
                "payload": json.dumps({
                    "source": "edgar",
                    "form_type": filing.form_type,
                    "content_hash": filing.content_hash,
                    "accession_no": filing.accession_no,
                    "company_name": filing.company_name,
                    "company_cik": filing.company_cik,
                    "filer_name": filing.filer_name,
                    "filed_at": filing.filed_at.isoformat(),
                }),
            },
        )
        self._db.commit()

    def close(self) -> None:
        self._client.close()


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point — quick smoke test without DB
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    print(f"\n{'='*60}")
    print(f"MeetMagus — SEC EDGAR Fetcher (dry run, last {days} days)")
    print(f"{'='*60}\n")

    fetcher = EdgarFetcher(db_session=None)
    result = fetcher.fetch_recent_filings(
        form_types=["SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"],
        since_days=days,
        max_results=50,
    )

    print(f"Form types:  {result.form_types}")
    print(f"Since:       {result.since_date}")
    print(f"Total found: {result.total_found}")
    print(f"New:         {result.new_ingestions}")
    print(f"Errors:      {len(result.errors)}")

    if result.filings:
        print(f"\n{'─'*60}")
        print("FILINGS FOUND:")
        print(f"{'─'*60}")
        for f in result.filings[:20]:
            print(
                f"  [{f.form_type:10s}] {f.filed_at}  "
                f"{f.company_name[:40]:<40}  filer: {f.filer_name[:30]}"
            )

    if result.errors:
        print(f"\nERRORS:")
        for e in result.errors:
            print(f"  {e}")

    fetcher.close()
