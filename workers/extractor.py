"""
app/workers/extractor.py
Extraction worker — reads pending jobs from platform.job_queue,
calls Groq (llama-3.1-8b-instant) to parse raw filing content,
and writes structured observations to the appropriate obs_* table.

Pipeline per job:
  1. Fetch raw_ingestion record (content + metadata)
  2. Route to correct prompt builder by form_type
  3. Call LLM for structured extraction
  4. Parse + validate JSON response
  5. Resolve company_id from company name (entity resolution)
  6. Write to obs_investor / obs_financial / obs_competitive / obs_employee
  7. Mark job as "completed"; on failure mark "failed" with error detail

Usage:
  # Process all pending ingest_source jobs once (batch mode):
  python -m app.workers.extractor

  # Process continuously (daemon mode):
  python -m app.workers.extractor --daemon --poll-seconds 30

  # Dry run (no DB writes, prints extraction output):
  python -m app.workers.extractor --dry-run
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractionResult:
    job_id: str
    accession_no: str
    form_type: str
    company_name: str
    status: str  # "completed" | "failed" | "skipped"
    observation_type: str = ""
    observation_id: str = ""
    extracted_data: dict = field(default_factory=dict)
    error: str = ""
    llm_tokens_used: int = 0


@dataclass
class BatchResult:
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[ExtractionResult] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# JSON parser — robust against LLM formatting quirks
# ──────────────────────────────────────────────────────────────────────────────

def parse_llm_json(raw: str) -> dict:
    """
    Parse JSON from LLM output. Handles common LLM formatting issues:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace
    - Single trailing commas before closing brace
    """
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        inner = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(inner).strip()

    # Strip single trailing comma before } or ]
    import re
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    return json.loads(text)


# ──────────────────────────────────────────────────────────────────────────────
# Extractor
# ──────────────────────────────────────────────────────────────────────────────

class Extractor:
    """
    Processes pending ingest_source jobs from platform.job_queue.

    Usage without DB (dry run):
        extractor = Extractor(db_session=None, llm_client=None)

    Usage with DB:
        extractor = Extractor(db_session=session)
        results = extractor.process_batch(limit=50)
    """

    def __init__(self, db_session=None, llm_client=None):
        self._db = db_session

        if llm_client is None and db_session is not None:
            from app.core.llm import LLMClient
            self._llm = LLMClient()
        else:
            self._llm = llm_client

    # ── Public API ────────────────────────────────────────────────────────────

    def process_batch(self, limit: int = 50) -> BatchResult:
        """
        Claim and process up to `limit` pending ingest_source jobs.
        Returns a BatchResult summary.
        """
        batch = BatchResult()
        jobs = self._claim_jobs(limit)
        batch.total_jobs = len(jobs)

        for job in jobs:
            result = self._process_one(job)
            batch.results.append(result)
            if result.status == "completed":
                batch.completed += 1
            elif result.status == "failed":
                batch.failed += 1
            else:
                batch.skipped += 1

        return batch

    def extract_from_payload(
        self,
        payload: dict,
        dry_run: bool = False,
    ) -> ExtractionResult:
        """
        Extract from a job payload dict without touching the job queue.
        Used for testing and dry runs.

        payload must have: form_type, company_name, filer_name, content_hash
        plus optionally: raw_text (if not provided, fetched from raw_ingestions)
        """
        from app.workers.prompts.edgar import build_extraction_messages

        form_type = payload.get("form_type", "")
        company_name = payload.get("company_name", "")
        filer_name = payload.get("filer_name", "")
        accession_no = payload.get("accession_no", "")
        raw_text = payload.get("raw_text", "")

        # If raw_text not in payload, fetch from DB
        if not raw_text and self._db:
            content_hash = payload.get("content_hash", "")
            raw_text = self._fetch_raw_content(content_hash)

        if not raw_text:
            return ExtractionResult(
                job_id="",
                accession_no=accession_no,
                form_type=form_type,
                company_name=company_name,
                status="skipped",
                error="No raw_text available",
            )

        messages, obs_type = build_extraction_messages(
            form_type=form_type,
            company_name=company_name,
            filer_name=filer_name,
            raw_text=raw_text,
        )

        # Call LLM
        extracted, tokens = self._call_llm(messages)
        if extracted is None:
            return ExtractionResult(
                job_id="",
                accession_no=accession_no,
                form_type=form_type,
                company_name=company_name,
                status="failed",
                error="LLM extraction failed",
            )

        result = ExtractionResult(
            job_id="",
            accession_no=accession_no,
            form_type=form_type,
            company_name=company_name,
            status="completed",
            observation_type=obs_type,
            extracted_data=extracted,
            llm_tokens_used=tokens,
        )

        if not dry_run and self._db:
            obs_id = self._write_observation(payload, obs_type, extracted)
            result.observation_id = obs_id

        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _process_one(self, job: dict) -> ExtractionResult:
        job_id = str(job.get("id", ""))
        payload = job.get("payload", {})
        if isinstance(payload, str):
            payload = json.loads(payload)

        self._update_job_status(job_id, "processing")

        try:
            result = self.extract_from_payload(payload, dry_run=False)
            result.job_id = job_id
            self._update_job_status(
                job_id, "completed",
                tokens_used=result.llm_tokens_used,
            )
            return result
        except Exception as e:
            logger.error("Extraction failed for job %s: %s", job_id, e, exc_info=True)
            self._update_job_status(job_id, "failed", error=str(e))
            return ExtractionResult(
                job_id=job_id,
                accession_no=payload.get("accession_no", ""),
                form_type=payload.get("form_type", ""),
                company_name=payload.get("company_name", ""),
                status="failed",
                error=str(e),
            )

    def _call_llm(self, messages: list[dict]) -> tuple[dict | None, int]:
        """
        Call LLM with retry. Returns (parsed_dict, tokens_used) or (None, 0).
        """
        if self._llm is None:
            raise RuntimeError("No LLM client configured")

        response = self._llm.complete(
            task="extraction",
            messages=messages,
            response_format={"type": "json_object"},
        )

        tokens = response.usage.total_tokens if response.usage else 0
        raw = response.choices[0].message.content

        try:
            parsed = parse_llm_json(raw)
            return parsed, tokens
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", e, raw[:500])
            return None, tokens

    def _write_observation(
        self,
        payload: dict,
        obs_type: str,
        extracted: dict,
    ) -> str:
        """Write extracted data to the appropriate obs_* table. Returns obs UUID."""
        from sqlalchemy import text

        company_id = self._resolve_company_id(payload.get("company_name", ""))
        filed_at = payload.get("filed_at", datetime.now(timezone.utc).isoformat())

        if obs_type in ("investor", "8k_classified"):
            actual_type = self._classify_8k(extracted) if obs_type == "8k_classified" else "investor"
            if actual_type == "investor":
                return self._write_obs_investor(company_id, filed_at, payload, extracted)
            elif actual_type == "financial":
                return self._write_obs_financial(company_id, filed_at, payload, extracted)
            elif actual_type == "competitive":
                return self._write_obs_competitive(company_id, filed_at, payload, extracted)
            elif actual_type == "employee":
                return self._write_obs_org_events(company_id, filed_at, payload, extracted)

        return ""

    def _classify_8k(self, extracted: dict) -> str:
        """Determine target table from 8-K extraction result."""
        obs_type = extracted.get("observation_type", "financial")
        mapping = {
            "financial": "financial",
            "competitive": "competitive",
            "employee": "employee",
        }
        return mapping.get(obs_type, "financial")

    def _write_obs_investor(
        self, company_id: str | None, filed_at: str, payload: dict, data: dict
    ) -> str:
        from sqlalchemy import text
        result = self._db.execute(
            text("""
                INSERT INTO global.obs_investor (
                    company_id, observed_at, source_id, confidence, status,
                    signal_type, investor_name, stake_pct, filing_type,
                    is_activist, headline, detail, metadata
                ) VALUES (
                    :company_id, :observed_at, 'edgar', 0.95, 'active',
                    :signal_type, :investor_name, :stake_pct, :filing_type,
                    :is_activist, :headline, :detail, :metadata::jsonb
                )
                RETURNING id
            """),
            {
                "company_id": company_id,
                "observed_at": filed_at,
                "signal_type": data.get("signal_type", "ownership_change"),
                "investor_name": data.get("investor_name", payload.get("filer_name", "")),
                "stake_pct": data.get("stake_pct"),
                "filing_type": data.get("filing_type", payload.get("form_type", "")),
                "is_activist": data.get("is_activist", False),
                "headline": data.get("headline", ""),
                "detail": data.get("detail", ""),
                "metadata": json.dumps({
                    "accession_no": payload.get("accession_no"),
                    "purpose_of_transaction": data.get("purpose_of_transaction"),
                    "has_board_demand": data.get("has_board_demand", False),
                    "has_sale_demand": data.get("has_sale_demand", False),
                    "shares_held": data.get("shares_held"),
                    "document_url": payload.get("document_url", ""),
                }),
            },
        )
        self._db.commit()
        row = result.fetchone()
        return str(row[0]) if row else ""

    def _write_obs_financial(
        self, company_id: str | None, filed_at: str, payload: dict, data: dict
    ) -> str:
        from sqlalchemy import text
        fin = data.get("financial") or {}
        result = self._db.execute(
            text("""
                INSERT INTO global.obs_financial (
                    company_id, observed_at, source_id, confidence, status,
                    signal_type, headline, detail, metric_name,
                    metric_value, metric_unit, amount_usd, metadata
                ) VALUES (
                    :company_id, :observed_at, 'edgar', 0.9, 'active',
                    :signal_type, :headline, :detail, :metric_name,
                    :metric_value, :metric_unit, :amount_usd, :metadata::jsonb
                )
                RETURNING id
            """),
            {
                "company_id": company_id,
                "observed_at": filed_at,
                "signal_type": fin.get("signal_type", "revenue_signal"),
                "headline": data.get("headline", ""),
                "detail": data.get("detail", ""),
                "metric_name": fin.get("metric_name"),
                "metric_value": fin.get("metric_value"),
                "metric_unit": fin.get("metric_unit"),
                "amount_usd": fin.get("amount_usd"),
                "metadata": json.dumps({
                    "accession_no": payload.get("accession_no"),
                    "event_category": data.get("event_category"),
                }),
            },
        )
        self._db.commit()
        row = result.fetchone()
        return str(row[0]) if row else ""

    def _write_obs_competitive(
        self, company_id: str | None, filed_at: str, payload: dict, data: dict
    ) -> str:
        from sqlalchemy import text
        comp = data.get("competitive") or {}
        result = self._db.execute(
            text("""
                INSERT INTO global.obs_competitive (
                    company_id, observed_at, source_id, confidence, status,
                    signal_type, headline, detail, metadata
                ) VALUES (
                    :company_id, :observed_at, 'edgar', 0.9, 'active',
                    :signal_type, :headline, :detail, :metadata::jsonb
                )
                RETURNING id
            """),
            {
                "company_id": company_id,
                "observed_at": filed_at,
                "signal_type": comp.get("signal_type", "acquisition"),
                "headline": data.get("headline", ""),
                "detail": data.get("detail", ""),
                "metadata": json.dumps({
                    "accession_no": payload.get("accession_no"),
                    "counterparty_name": comp.get("counterparty_name"),
                    "deal_value_usd": comp.get("deal_value_usd"),
                }),
            },
        )
        self._db.commit()
        row = result.fetchone()
        return str(row[0]) if row else ""

    def _write_obs_org_events(
        self, company_id: str | None, filed_at: str, payload: dict, data: dict
    ) -> str:
        """Write to obs_org_events (replaces old obs_employee table)."""
        from sqlalchemy import text
        emp = data.get("employee") or {}
        person_title = emp.get("person_title", "")
        # Detect strategic roles that signal intent
        strategic_titles = {
            "investor relations": "ipo_prep",
            "general counsel": "ma_signal",
            "chief accounting": "ipo_prep",
            "corporate development": "ma_signal",
            "chief revenue": "growth_signal",
            "market access": "commercial_launch",
            "regulatory affairs": "new_program",
        }
        is_strategic = False
        strategic_signal = None
        for keyword, signal in strategic_titles.items():
            if keyword in person_title.lower():
                is_strategic = True
                strategic_signal = signal
                break

        result = self._db.execute(
            text("""
                INSERT INTO global.obs_org_events (
                    company_id, observed_at, source_id, confidence, status,
                    signal_type, headline, detail, person_name, person_title,
                    department, is_strategic, strategic_signal, metadata
                ) VALUES (
                    :company_id, :observed_at, 'edgar', 0.9, 'active',
                    :signal_type, :headline, :detail, :person_name, :person_title,
                    :department, :is_strategic, :strategic_signal, :metadata::jsonb
                )
                RETURNING id
            """),
            {
                "company_id": company_id,
                "observed_at": filed_at,
                "signal_type": emp.get("signal_type", "org_change"),
                "headline": data.get("headline", ""),
                "detail": data.get("detail", ""),
                "person_name": emp.get("person_name"),
                "person_title": person_title,
                "department": emp.get("department"),
                "is_strategic": is_strategic,
                "strategic_signal": strategic_signal,
                "metadata": json.dumps({
                    "accession_no": payload.get("accession_no"),
                }),
            },
        )
        self._db.commit()
        row = result.fetchone()
        return str(row[0]) if row else ""

    def _resolve_company_id(self, company_name: str) -> str | None:
        """
        Look up canonical company_id by name or alias.
        Returns UUID string or None if not found.
        """
        if not self._db or not company_name:
            return None
        from sqlalchemy import text
        # Try exact match first
        row = self._db.execute(
            text("""
                SELECT id FROM global.companies
                WHERE lower(name) = lower(:name) LIMIT 1
            """),
            {"name": company_name},
        ).fetchone()
        if row:
            return str(row[0])
        # Try alias table
        row = self._db.execute(
            text("""
                SELECT company_id FROM global.company_aliases
                WHERE lower(alias) = lower(:name)
                  AND status = 'confirmed'
                LIMIT 1
            """),
            {"name": company_name},
        ).fetchone()
        return str(row[0]) if row else None

    def _fetch_raw_content(self, content_hash: str) -> str:
        if not self._db or not content_hash:
            return ""
        from sqlalchemy import text
        row = self._db.execute(
            text("""
                SELECT raw_content FROM platform.raw_ingestions
                WHERE content_hash = :hash LIMIT 1
            """),
            {"hash": content_hash},
        ).fetchone()
        return row[0] if row else ""

    def _claim_jobs(self, limit: int) -> list[dict]:
        """Atomically claim pending jobs to prevent double-processing."""
        if not self._db:
            return []
        from sqlalchemy import text
        rows = self._db.execute(
            text("""
                UPDATE platform.job_queue
                SET status = 'claimed',
                    updated_at = NOW()
                WHERE id IN (
                    SELECT id FROM platform.job_queue
                    WHERE job_type = 'ingest_source'
                      AND status = 'pending'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, job_type, payload, priority
            """),
            {"limit": limit},
        ).fetchall()
        self._db.commit()
        return [{"id": r[0], "job_type": r[1], "payload": r[2], "priority": r[3]} for r in rows]

    def _update_job_status(
        self,
        job_id: str,
        status: str,
        tokens_used: int = 0,
        error: str = "",
    ) -> None:
        if not self._db:
            return
        from sqlalchemy import text
        self._db.execute(
            text("""
                UPDATE platform.job_queue
                SET status = :status,
                    updated_at = NOW(),
                    llm_tokens_used = llm_tokens_used + :tokens,
                    error_detail = CASE WHEN :error != '' THEN :error ELSE error_detail END
                WHERE id = :job_id
            """),
            {
                "status": status,
                "tokens": tokens_used,
                "error": error,
                "job_id": job_id,
            },
        )
        self._db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="DealFlow extraction worker")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if args.dry_run:
        # Demo: extract the Jana/Alkami 13D scenario from hardcoded payload
        print("\n" + "="*60)
        print("DealFlow Extractor — DRY RUN (Jana/Alkami 13D scenario)")
        print("="*60 + "\n")

        from app.core.llm import LLMClient
        llm = LLMClient()
        extractor = Extractor(db_session=None, llm_client=llm)

        demo_payload = {
            "form_type": "SC 13D",
            "company_name": "Alkami Technology, Inc.",
            "filer_name": "Jana Partners LLC",
            "accession_no": "0000902664-26-001234",
            "filed_at": "2026-05-28",
            "raw_text": (
                "SCHEDULE 13D\n\n"
                "CUSIP No. 01626W109\n\n"
                "Item 1. Security and Issuer\n"
                "This statement relates to the Common Stock of Alkami Technology, Inc. "
                "(the 'Issuer'), a Delaware corporation. The principal executive offices "
                "of the Issuer are located at 5601 Granite Pkwy, Suite 120, Plano, TX 75024.\n\n"
                "Item 2. Identity and Background\n"
                "This statement is being filed by Jana Partners LLC, a Delaware limited "
                "liability company ('Jana Partners'). Jana Partners is an investment adviser "
                "that manages private investment funds.\n\n"
                "Item 4. Purpose of Transaction\n"
                "Jana Partners acquired the Shares because it believes the Shares are "
                "undervalued and represent an attractive investment opportunity. Jana Partners "
                "intends to engage in discussions with the Issuer's management and board of "
                "directors regarding the Issuer's business, operations, financial performance, "
                "strategic alternatives including a potential sale of the company, and other "
                "matters that could enhance shareholder value.\n\n"
                "Item 5. Interest in Securities of the Issuer\n"
                "(a) Jana Partners beneficially owns 7,234,521 shares, representing "
                "approximately 7.9% of the outstanding Common Stock.\n\n"
            ),
        }

        result = extractor.extract_from_payload(demo_payload, dry_run=True)
        print(f"Status:    {result.status}")
        print(f"Obs type:  {result.observation_type}")
        print(f"Tokens:    {result.llm_tokens_used}")
        print(f"\nExtracted data:")
        print(json.dumps(result.extracted_data, indent=2))
        if result.error:
            print(f"\nError: {result.error}")

    elif args.daemon:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise SystemExit("DATABASE_URL not set")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        engine = create_engine(db_url)
        print(f"Daemon mode — polling every {args.poll_seconds}s")
        while True:
            with Session(engine) as session:
                extractor = Extractor(db_session=session)
                batch = extractor.process_batch(limit=args.limit)
                if batch.total_jobs > 0:
                    print(
                        f"Batch: {batch.total_jobs} jobs — "
                        f"{batch.completed} completed, {batch.failed} failed"
                    )
            time.sleep(args.poll_seconds)

    else:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise SystemExit("DATABASE_URL not set. Use --dry-run for demo.")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        engine = create_engine(db_url)
        with Session(engine) as session:
            extractor = Extractor(db_session=session)
            batch = extractor.process_batch(limit=args.limit)
        print(f"Done: {batch.completed} completed, {batch.failed} failed, {batch.skipped} skipped")
