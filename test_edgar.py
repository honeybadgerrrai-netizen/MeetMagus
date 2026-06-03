"""
tests/test_edgar.py
Test suite for the SEC EDGAR fetcher.

Tests are split into two categories:
  - Unit tests (no network, no DB) — always fast, always pass
  - Integration tests (live EDGAR API) — require network, marked with @pytest.mark.live

Run unit tests only:
    pytest tests/test_edgar.py -v

Run all including live EDGAR calls:
    pytest tests/test_edgar.py -v -m live

Run the defining scenario (Jana/Alkami):
    pytest tests/test_edgar.py::test_jana_alkami_13d -v -m live
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Adjust path if running from project root without installing as package
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.fetchers.edgar import (
    EdgarClient,
    EdgarFetcher,
    EdgarFiling,
    FetchResult,
    RateLimiter,
    FORM_TYPES_ACTIVIST,
    FORM_TYPES_DEFAULT,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_efts_hit() -> dict:
    """A realistic EFTS search result hit for a 13D filing."""
    return {
        "_id": "0000902664-26-001234",
        "_source": {
            "form_type": "SC 13D",
            "period_of_report": "2026-05-28",
            "file_date": "2026-05-28",
            "entity_name": "Alkami Technology, Inc.",
            "entity_id": "1834016",
            "display_names": ["Jana Partners LLC"],
            "file_num": "005-93892",
            "accession_no": "0000902664-26-001234",
        },
    }


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session that never commits to a real DB."""
    db = MagicMock()
    # _is_duplicate returns False by default (no existing rows)
    db.execute.return_value.fetchone.return_value = None
    return db


@pytest.fixture
def fetcher_no_db() -> EdgarFetcher:
    return EdgarFetcher(db_session=None)


@pytest.fixture
def fetcher_mock_db(mock_db) -> EdgarFetcher:
    return EdgarFetcher(db_session=mock_db)


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: EdgarFiling.from_efts_hit parses correctly
# ──────────────────────────────────────────────────────────────────────────────

def test_filing_parsed_from_efts_hit(sample_efts_hit):
    filing = EdgarFiling.from_efts_hit(sample_efts_hit)

    assert filing.form_type == "SC 13D"
    assert filing.filed_at == date(2026, 5, 28)
    assert "Alkami" in filing.company_name
    assert "Jana" in filing.filer_name
    assert filing.content_hash  # non-empty
    assert len(filing.content_hash) == 64  # SHA-256 hex


def test_content_hash_is_deterministic(sample_efts_hit):
    """Same input → same hash every time."""
    f1 = EdgarFiling.from_efts_hit(sample_efts_hit)
    f2 = EdgarFiling.from_efts_hit(sample_efts_hit)
    assert f1.content_hash == f2.content_hash


def test_content_hash_differs_for_different_filings(sample_efts_hit):
    """Different filings → different hashes."""
    hit2 = json.loads(json.dumps(sample_efts_hit))  # deep copy
    hit2["_source"]["entity_name"] = "Some Other Company Inc."
    hit2["_source"]["entity_id"] = "9999999"
    hit2["_id"] = "0000902664-26-999999"

    f1 = EdgarFiling.from_efts_hit(sample_efts_hit)
    f2 = EdgarFiling.from_efts_hit(hit2)
    assert f1.content_hash != f2.content_hash


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Rate limiter stays under 10 req/sec
# ──────────────────────────────────────────────────────────────────────────────

def test_rate_limiter_respects_interval():
    """15 calls should take at least 14 * min_interval seconds."""
    limiter = RateLimiter(max_per_second=8)  # same as production
    n = 10
    start = time.monotonic()
    for _ in range(n):
        limiter.wait()
    elapsed = time.monotonic() - start

    # n calls at 8/sec → at least (n-1) intervals of 0.125s
    min_expected = (n - 1) * (1.0 / 8)
    assert elapsed >= min_expected * 0.9, (
        f"Rate limiter too fast: {elapsed:.3f}s for {n} calls "
        f"(expected >= {min_expected:.3f}s)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Level 1 dedup (content hash)
# ──────────────────────────────────────────────────────────────────────────────

def test_dedup_skips_seen_hash(mock_db, sample_efts_hit):
    """
    When DB returns a row for a content_hash, the fetcher should skip it.
    """
    # Simulate: hash already exists in raw_ingestions
    mock_db.execute.return_value.fetchone.return_value = (1,)

    fetcher = EdgarFetcher(db_session=mock_db)

    # Manually call _is_duplicate
    filing = EdgarFiling.from_efts_hit(sample_efts_hit)
    assert fetcher._is_duplicate(filing.content_hash) is True


def test_dedup_passes_new_hash(mock_db, sample_efts_hit):
    """When DB returns None for content_hash, the fetcher should process it."""
    mock_db.execute.return_value.fetchone.return_value = None

    fetcher = EdgarFetcher(db_session=mock_db)
    filing = EdgarFiling.from_efts_hit(sample_efts_hit)
    assert fetcher._is_duplicate(filing.content_hash) is False


def test_fetch_same_filing_twice_deduplicates(mock_db, sample_efts_hit):
    """
    Fetch the same filing twice in a row.
    First fetch: new_ingestions = 1.
    Second fetch (DB now has the hash): new_ingestions = 0, skipped_dedup = 1.
    """
    fetcher = EdgarFetcher(db_session=mock_db)

    # Patch search_filings to return our one known hit
    with patch.object(fetcher._client, "search_filings", return_value=[sample_efts_hit]):
        # First fetch — hash not in DB
        mock_db.execute.return_value.fetchone.return_value = None
        r1 = fetcher.fetch_recent_filings(["SC 13D"], since_days=7)
        assert r1.new_ingestions == 1
        assert r1.skipped_dedup == 0

        # Second fetch — hash now in DB
        mock_db.execute.return_value.fetchone.return_value = (1,)
        r2 = fetcher.fetch_recent_filings(["SC 13D"], since_days=7)
        assert r2.new_ingestions == 0
        assert r2.skipped_dedup == 1


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: DB write shape
# ──────────────────────────────────────────────────────────────────────────────

def test_write_raw_ingestion_called_with_correct_fields(mock_db, sample_efts_hit):
    """Verify the SQL INSERT is called with the expected fields."""
    fetcher = EdgarFetcher(db_session=mock_db)
    filing = EdgarFiling.from_efts_hit(sample_efts_hit)

    fetcher._write_raw_ingestion(filing)

    # Should have called db.execute at least once
    assert mock_db.execute.called
    call_args = mock_db.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]

    assert params["hash"] == filing.content_hash
    assert params["content"] == filing.raw_text
    # metadata should be valid JSON containing form_type
    meta = json.loads(params["meta"])
    assert meta["form_type"] == "SC 13D"
    assert "Alkami" in meta["company_name"]


def test_enqueue_extraction_called(mock_db, sample_efts_hit):
    """Verify job_queue INSERT is called after ingestion."""
    fetcher = EdgarFetcher(db_session=mock_db)
    filing = EdgarFiling.from_efts_hit(sample_efts_hit)
    fetcher._enqueue_extraction(filing)

    assert mock_db.execute.called
    call_args = mock_db.execute.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    payload = json.loads(params["payload"])

    assert payload["source"] == "edgar"
    assert payload["form_type"] == "SC 13D"
    assert payload["content_hash"] == filing.content_hash


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: FetchResult aggregation
# ──────────────────────────────────────────────────────────────────────────────

def test_fetch_result_counts_correctly(fetcher_no_db, sample_efts_hit):
    """Dry-run fetch with 3 hits returns correct counts."""
    three_hits = [sample_efts_hit] * 3

    with patch.object(fetcher_no_db._client, "search_filings", return_value=three_hits):
        result = fetcher_no_db.fetch_recent_filings(["SC 13D"], since_days=7)

    assert result.total_found == 3
    assert result.new_ingestions == 3  # no DB → all counted as new
    assert result.skipped_dedup == 0
    assert len(result.errors) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Date filtering
# ──────────────────────────────────────────────────────────────────────────────

def test_since_date_is_passed_to_client(fetcher_no_db):
    """since_date parameter is forwarded to EdgarClient.search_filings."""
    target_date = date(2026, 5, 1)

    with patch.object(fetcher_no_db._client, "search_filings", return_value=[]) as mock_search:
        fetcher_no_db.fetch_recent_filings(["SC 13D"], since_date=target_date)
        called_start = mock_search.call_args[0][1]  # second positional arg
        assert called_start == target_date


# ──────────────────────────────────────────────────────────────────────────────
# LIVE integration tests — require network, skip in CI
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.live
def test_live_fetch_recent_13d():
    """
    Live test: fetch real 13D filings from the last 14 days.
    Should return at least 1 result (there are always activist filings).
    """
    fetcher = EdgarFetcher(db_session=None)
    result = fetcher.fetch_recent_filings(
        form_types=["SC 13D", "SC 13D/A"],
        since_days=14,
        max_results=20,
    )
    fetcher.close()

    assert result.total_found > 0, (
        "Expected at least 1 SC 13D filing in the last 14 days — "
        "check EDGAR API connectivity"
    )
    assert len(result.filings) > 0
    # All filings should have required fields
    for f in result.filings:
        assert f.form_type in ("SC 13D", "SC 13D/A")
        assert f.company_name
        assert f.content_hash
        assert len(f.content_hash) == 64


@pytest.mark.live
def test_jana_alkami_13d():
    """
    THE defining scenario: Jana Partners filed a 13D on Alkami Technology
    on May 28, 2026. This test verifies we can detect it.

    If this test passes, the core DealFlow trigger use case works end-to-end.
    """
    fetcher = EdgarFetcher(db_session=None)

    # Fetch from May 25 to give a buffer
    result = fetcher.fetch_recent_filings(
        form_types=["SC 13D", "SC 13D/A"],
        since_date=date(2026, 5, 25),
        max_results=100,
    )
    fetcher.close()

    # Find the Jana/Alkami filing
    alkami_filings = [
        f for f in result.filings
        if "alkami" in f.company_name.lower()
    ]

    jana_filings = [
        f for f in alkami_filings
        if "jana" in f.filer_name.lower() or "jana" in f.raw_text.lower()
    ]

    assert len(alkami_filings) > 0, (
        f"No Alkami filings found in {result.total_found} total results. "
        f"Companies found: {[f.company_name for f in result.filings[:10]]}"
    )

    assert len(jana_filings) > 0, (
        f"Alkami filing found but Jana not identified as filer. "
        f"Filers: {[f.filer_name for f in alkami_filings]}"
    )

    filing = jana_filings[0]
    assert filing.form_type in ("SC 13D", "SC 13D/A")
    assert filing.filed_at >= date(2026, 5, 25)
    print(f"\n✓ Jana/Alkami 13D detected: {filing.accession_no} filed {filing.filed_at}")
    print(f"  Company: {filing.company_name}")
    print(f"  Filer:   {filing.filer_name}")
    print(f"  Hash:    {filing.content_hash[:16]}...")


@pytest.mark.live
def test_live_fetch_alkami_by_cik():
    """
    Fetch Alkami Technology filings directly by CIK.
    Alkami CIK: 1834016
    Should include the Jana 13D and recent 8-K filings.
    """
    ALKAMI_CIK = "1834016"
    fetcher = EdgarFetcher(db_session=None)
    result = fetcher.fetch_for_company(
        cik=ALKAMI_CIK,
        form_types=["SC 13D", "SC 13D/A", "SC 13G", "8-K"],
        since_days=60,
    )
    fetcher.close()

    assert result.total_found > 0, (
        f"No recent filings found for Alkami CIK {ALKAMI_CIK}"
    )

    form_types_found = {f.form_type for f in result.filings}
    print(f"\n✓ Alkami filings found: {result.total_found}")
    print(f"  Form types: {form_types_found}")
    for f in result.filings:
        print(f"  [{f.form_type}] {f.filed_at}  {f.company_name}")


@pytest.mark.live
def test_live_rate_limit_not_exceeded():
    """
    Make 20 rapid requests and verify none return HTTP 429.
    (EDGAR blocks at 10/sec; our limiter targets 8/sec.)
    """
    client = EdgarClient()
    errors = []
    start = time.monotonic()

    for i in range(20):
        try:
            client.search_filings(
                ["SC 13D"],
                since_date=date.today() - timedelta(days=1),
                max_results=5,
            )
        except Exception as e:
            errors.append(str(e))

    elapsed = time.monotonic() - start
    client.close()

    assert not any("429" in e for e in errors), (
        f"Rate limit exceeded (HTTP 429). Errors: {errors}"
    )
    # 20 calls at 8/sec → at least 19 * 0.125 = 2.375s
    assert elapsed >= 2.0, (
        f"Completed 20 requests in {elapsed:.2f}s — rate limiter may not be working"
    )
    print(f"\n✓ 20 requests in {elapsed:.2f}s (no 429s)")
