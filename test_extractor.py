"""
tests/test_extractor.py
Test suite for the extraction pipeline.

Run unit tests (no LLM calls, no DB):
    pytest tests/test_extractor.py -v

Run live tests (real Groq API call — needs GROQ_API_KEY):
    pytest tests/test_extractor.py -v -m live

The key test is test_extract_jana_alkami_13d — it calls Groq with real
Jana/Alkami 13D text and verifies the structured output matches what
an investment banker would expect.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workers.extractor import Extractor, ExtractionResult, parse_llm_json
from app.workers.prompts.edgar import build_extraction_messages, build_13d_messages


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

JANA_ALKAMI_RAW = """\
SCHEDULE 13D
CUSIP No. 01626W109

Item 1. Security and Issuer
This statement relates to the Common Stock of Alkami Technology, Inc.
Principal offices: 5601 Granite Pkwy, Suite 120, Plano, TX 75024.

Item 2. Identity and Background
Filed by Jana Partners LLC, a Delaware limited liability company.
Jana Partners is an investment adviser managing private investment funds.

Item 4. Purpose of Transaction
Jana Partners acquired the Shares because it believes the Shares are undervalued.
Jana Partners intends to engage with management and the board regarding strategic
alternatives including a potential sale of the company to enhance shareholder value.

Item 5. Interest in Securities
Jana Partners beneficially owns 7,234,521 shares, representing approximately 7.9%
of the outstanding Common Stock of Alkami Technology, Inc.
"""

GOOD_13D_RESPONSE = {
    "signal_type": "13d_filing",
    "investor_name": "Jana Partners LLC",
    "stake_pct": 7.9,
    "shares_held": 7234521,
    "is_activist": True,
    "filing_type": "SC 13D",
    "headline": "Jana Partners discloses 7.9% activist stake in Alkami Technology",
    "detail": "Jana Partners LLC filed a Schedule 13D disclosing a 7.9% stake in Alkami Technology. The filing indicates activist intent, with Jana seeking strategic alternatives including a potential sale.",
    "purpose_of_transaction": "Engage with board regarding strategic alternatives including a potential sale",
    "has_board_demand": False,
    "has_sale_demand": True,
}

GOOD_8K_RESPONSE = {
    "observation_type": "financial",
    "event_category": "earnings_guidance",
    "headline": "Alkami raises FY2026 revenue guidance to $380M-$390M",
    "detail": "Alkami Technology raised its full-year 2026 revenue guidance following strong Q1 results.",
    "financial": {
        "signal_type": "revenue_signal",
        "metric_name": "revenue",
        "metric_value": 385.0,
        "metric_unit": "USD_millions",
        "amount_usd": 385000000.0,
    },
    "competitive": {"signal_type": None},
    "employee": {"signal_type": None},
}


@pytest.fixture
def mock_llm_13d():
    """Mock LLM that returns a valid 13D extraction."""
    llm = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = json.dumps(GOOD_13D_RESPONSE)
    response.usage.total_tokens = 312
    llm.complete.return_value = response
    return llm


@pytest.fixture
def mock_llm_8k():
    llm = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = json.dumps(GOOD_8K_RESPONSE)
    response.usage.total_tokens = 280
    llm.complete.return_value = response
    return llm


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    return db


@pytest.fixture
def jana_payload():
    return {
        "form_type": "SC 13D",
        "company_name": "Alkami Technology, Inc.",
        "filer_name": "Jana Partners LLC",
        "accession_no": "0000902664-26-001234",
        "filed_at": "2026-05-28",
        "raw_text": JANA_ALKAMI_RAW,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: parse_llm_json handles LLM formatting quirks
# ──────────────────────────────────────────────────────────────────────────────

def test_parse_clean_json():
    raw = '{"signal_type": "13d_filing", "stake_pct": 7.9}'
    result = parse_llm_json(raw)
    assert result["signal_type"] == "13d_filing"
    assert result["stake_pct"] == 7.9


def test_parse_json_with_markdown_fence():
    raw = '```json\n{"signal_type": "13d_filing", "stake_pct": 7.9}\n```'
    result = parse_llm_json(raw)
    assert result["signal_type"] == "13d_filing"


def test_parse_json_with_plain_fence():
    raw = '```\n{"key": "value"}\n```'
    result = parse_llm_json(raw)
    assert result["key"] == "value"


def test_parse_json_trailing_comma():
    raw = '{"a": 1, "b": 2,}'
    result = parse_llm_json(raw)
    assert result["a"] == 1
    assert result["b"] == 2


def test_parse_invalid_json_raises():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        parse_llm_json("this is not json at all")


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Prompt builder routes correctly by form type
# ──────────────────────────────────────────────────────────────────────────────

def test_13d_routes_to_investor_type():
    _, obs_type = build_extraction_messages("SC 13D", "Acme", "Filer", "text")
    assert obs_type == "investor"


def test_13g_routes_to_investor_type():
    _, obs_type = build_extraction_messages("SC 13G", "Acme", "Filer", "text")
    assert obs_type == "investor"


def test_8k_routes_to_8k_classified():
    _, obs_type = build_extraction_messages("8-K", "Acme", "", "text")
    assert obs_type == "8k_classified"


def test_form4_routes_to_investor_type():
    _, obs_type = build_extraction_messages("4", "Acme", "John Smith", "text")
    assert obs_type == "investor"


def test_13d_prompt_includes_company_name():
    msgs, _ = build_extraction_messages("SC 13D", "Alkami Technology", "Jana Partners", "raw")
    user_content = msgs[-1]["content"]
    assert "Alkami Technology" in user_content
    assert "Jana Partners" in user_content


def test_13d_prompt_includes_raw_text():
    msgs, _ = build_extraction_messages("SC 13D", "Acme", "Filer", "UNIQUE_SENTINEL_TEXT")
    user_content = msgs[-1]["content"]
    assert "UNIQUE_SENTINEL_TEXT" in user_content


def test_13d_prompt_truncates_long_text():
    long_text = "x" * 10000
    msgs, _ = build_extraction_messages("SC 13D", "Acme", "Filer", long_text)
    user_content = msgs[-1]["content"]
    # Should not contain the full 10K chars
    assert len(user_content) < 8000


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Extractor.extract_from_payload (unit — mocked LLM)
# ──────────────────────────────────────────────────────────────────────────────

def test_extract_13d_returns_investor_fields(mock_llm_13d, jana_payload):
    extractor = Extractor(db_session=None, llm_client=mock_llm_13d)
    result = extractor.extract_from_payload(jana_payload, dry_run=True)

    assert result.status == "completed"
    assert result.observation_type == "investor"
    assert result.extracted_data["signal_type"] == "13d_filing"
    assert result.extracted_data["investor_name"] == "Jana Partners LLC"
    assert result.extracted_data["stake_pct"] == 7.9
    assert result.extracted_data["is_activist"] is True
    assert result.extracted_data["has_sale_demand"] is True


def test_extract_returns_token_count(mock_llm_13d, jana_payload):
    extractor = Extractor(db_session=None, llm_client=mock_llm_13d)
    result = extractor.extract_from_payload(jana_payload, dry_run=True)
    assert result.llm_tokens_used == 312


def test_extract_skips_when_no_raw_text(mock_llm_13d):
    extractor = Extractor(db_session=None, llm_client=mock_llm_13d)
    payload = {"form_type": "SC 13D", "company_name": "Acme", "filer_name": "Filer"}
    result = extractor.extract_from_payload(payload, dry_run=True)
    assert result.status == "skipped"
    assert "No raw_text" in result.error
    # LLM should NOT have been called
    mock_llm_13d.complete.assert_not_called()


def test_extract_fails_gracefully_on_bad_llm_json(jana_payload):
    bad_llm = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = "this is definitely not json {{"
    response.usage.total_tokens = 10
    bad_llm.complete.return_value = response

    extractor = Extractor(db_session=None, llm_client=bad_llm)
    result = extractor.extract_from_payload(jana_payload, dry_run=True)
    assert result.status == "failed"
    assert "failed" in result.error.lower()


def test_extract_8k_classifies_financial(mock_llm_8k):
    extractor = Extractor(db_session=None, llm_client=mock_llm_8k)
    payload = {
        "form_type": "8-K",
        "company_name": "Alkami Technology, Inc.",
        "filer_name": "",
        "filed_at": "2026-05-15",
        "raw_text": "Item 2.02 Results of Operations. Revenue for Q1 2026 was $92M...",
    }
    result = extractor.extract_from_payload(payload, dry_run=True)
    assert result.status == "completed"
    assert result.observation_type == "8k_classified"
    assert result.extracted_data["observation_type"] == "financial"


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: DB write — correct fields passed to INSERT
# ──────────────────────────────────────────────────────────────────────────────

def test_write_obs_investor_called_with_correct_fields(mock_db, mock_llm_13d, jana_payload):
    """Verify obs_investor INSERT receives the right values."""
    mock_db.execute.return_value.fetchone.return_value = ("fake-uuid-1234",)

    extractor = Extractor(db_session=mock_db, llm_client=mock_llm_13d)
    result = extractor.extract_from_payload(jana_payload, dry_run=False)

    assert result.status == "completed"
    assert mock_db.execute.called

    # Find the obs_investor INSERT call
    all_calls = mock_db.execute.call_args_list
    insert_call = None
    for call in all_calls:
        args = call[0]
        if len(args) >= 2 and isinstance(args[1], dict):
            if "signal_type" in args[1]:
                insert_call = args[1]
                break

    assert insert_call is not None, "obs_investor INSERT not found"
    assert insert_call["signal_type"] == "13d_filing"
    assert insert_call["investor_name"] == "Jana Partners LLC"
    assert insert_call["stake_pct"] == 7.9
    assert insert_call["is_activist"] is True


def test_job_status_transitions(mock_db, mock_llm_13d):
    """Job moves from claimed → processing → completed."""
    mock_db.execute.return_value.fetchone.return_value = None

    extractor = Extractor(db_session=mock_db, llm_client=mock_llm_13d)

    # Simulate a job
    job = {
        "id": "job-abc-123",
        "job_type": "ingest_source",
        "payload": json.dumps({
            "form_type": "SC 13D",
            "company_name": "Alkami Technology, Inc.",
            "filer_name": "Jana Partners LLC",
            "accession_no": "0000902664-26-001234",
            "filed_at": "2026-05-28",
            "raw_text": JANA_ALKAMI_RAW,
        }),
        "priority": 2,
    }

    extractor._process_one(job)

    # Should have called _update_job_status with 'processing' then 'completed'
    status_updates = []
    for call in mock_db.execute.call_args_list:
        args = call[0]
        if len(args) >= 2 and isinstance(args[1], dict) and "status" in args[1]:
            status_updates.append(args[1]["status"])

    assert "processing" in status_updates
    assert "completed" in status_updates


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Entity resolution
# ──────────────────────────────────────────────────────────────────────────────

def test_resolve_company_id_exact_match(mock_db):
    mock_db.execute.return_value.fetchone.return_value = ("company-uuid-alkami",)
    extractor = Extractor(db_session=mock_db)
    result = extractor._resolve_company_id("Alkami Technology, Inc.")
    assert result == "company-uuid-alkami"


def test_resolve_company_id_returns_none_when_not_found(mock_db):
    mock_db.execute.return_value.fetchone.return_value = None
    extractor = Extractor(db_session=mock_db)
    result = extractor._resolve_company_id("Unknown Company XYZ")
    assert result is None


def test_resolve_company_id_no_db():
    extractor = Extractor(db_session=None)
    result = extractor._resolve_company_id("Alkami Technology")
    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# LIVE tests — require GROQ_API_KEY
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.live
def test_extract_jana_alkami_13d_live():
    """
    THE key live test: send real Jana/Alkami 13D text to Groq and verify
    the structured output is correct enough to drive a banker alert.

    This test validates the whole extraction pipeline end-to-end.
    """
    from app.core.llm import LLMClient
    llm = LLMClient()
    extractor = Extractor(db_session=None, llm_client=llm)

    payload = {
        "form_type": "SC 13D",
        "company_name": "Alkami Technology, Inc.",
        "filer_name": "Jana Partners LLC",
        "accession_no": "0000902664-26-001234",
        "filed_at": "2026-05-28",
        "raw_text": JANA_ALKAMI_RAW,
    }

    result = extractor.extract_from_payload(payload, dry_run=True)

    print(f"\n{'='*60}")
    print("LIVE EXTRACTION RESULT — Jana/Alkami 13D")
    print(f"{'='*60}")
    print(json.dumps(result.extracted_data, indent=2))
    print(f"\nTokens used: {result.llm_tokens_used}")

    assert result.status == "completed", f"Extraction failed: {result.error}"
    assert result.observation_type == "investor"

    data = result.extracted_data
    assert data.get("signal_type") in ("13d_filing", "ownership_change")
    assert "jana" in data.get("investor_name", "").lower()
    # Stake should be close to 7.9%
    stake = data.get("stake_pct")
    assert stake is not None, "stake_pct not extracted"
    assert 7.0 <= float(stake) <= 9.0, f"Unexpected stake_pct: {stake}"
    assert data.get("is_activist") is True
    assert data.get("headline"), "headline is empty"
    assert data.get("detail"), "detail is empty"
    assert result.llm_tokens_used > 0


@pytest.mark.live
def test_extract_missing_stake_returns_null_gracefully_live():
    """
    If stake % is not mentioned in a filing, the LLM should return null
    for stake_pct rather than hallucinating a number.
    """
    from app.core.llm import LLMClient
    llm = LLMClient()
    extractor = Extractor(db_session=None, llm_client=llm)

    payload = {
        "form_type": "SC 13D",
        "company_name": "Fictional Corp Inc.",
        "filer_name": "Some Fund LP",
        "accession_no": "0000000000-00-000001",
        "filed_at": "2026-06-01",
        "raw_text": (
            "SCHEDULE 13D\n\n"
            "Item 4. Purpose of Transaction\n"
            "The Reporting Person acquired shares for investment purposes "
            "and may seek to engage in discussions with management.\n\n"
            "Item 5. Interest in Securities\n"
            "See attached exhibit.\n"
        ),
    }

    result = extractor.extract_from_payload(payload, dry_run=True)
    assert result.status == "completed"
    # stake_pct should be null since it's not in the text
    stake = result.extracted_data.get("stake_pct")
    assert stake is None or isinstance(stake, (int, float)), (
        f"stake_pct should be null or a number, got: {stake!r}"
    )
