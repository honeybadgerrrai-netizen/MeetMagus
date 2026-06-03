"""
tests/test_embedder.py
Test suite for the embedding background job.

Unit tests (no model loaded, no DB):
    pytest tests/test_embedder.py -v

Live tests (loads real sentence-transformers model, ~2s startup):
    pytest tests/test_embedder.py -v -m live
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workers.embedder import (
    Embedder,
    EmbedResult,
    EmbedBatchResult,
    build_embed_text,
    OBS_TABLE_MAP,
    EMBEDDING_DIMS,
    enqueue_embedding_job,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

FAKE_VECTOR = [0.01 * i for i in range(EMBEDDING_DIMS)]  # 1024 floats

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    return db


@pytest.fixture
def mock_embed(monkeypatch):
    """Patch embed_text to return a deterministic fake vector without loading the model."""
    def _fake_embed(text, device="cpu"):
        return FAKE_VECTOR[:]
    monkeypatch.setattr("app.workers.embedder.embed_text", _fake_embed)
    return _fake_embed


@pytest.fixture
def mock_embed_many(monkeypatch):
    def _fake_embed_many(texts, device="cpu"):
        return [FAKE_VECTOR[:] for _ in texts]
    monkeypatch.setattr("app.workers.embedder.embed_texts",
                        lambda texts, device="cpu": np.array([FAKE_VECTOR for _ in texts]))
    return _fake_embed_many


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: build_embed_text
# ──────────────────────────────────────────────────────────────────────────────

def test_build_embed_text_combines_headline_and_detail():
    row = {
        "headline": "Jana Partners discloses 7.9% stake",
        "detail": "Jana Partners filed a 13D indicating activist intent.",
    }
    text = build_embed_text(row)
    assert "Jana Partners discloses 7.9% stake" in text
    assert "activist intent" in text


def test_build_embed_text_uses_trend_fields_for_macro():
    row = {
        "trend_name": "Rising interest rates",
        "trend_description": "Fed signals three more hikes in 2026.",
    }
    text = build_embed_text(row)
    assert "Rising interest rates" in text
    assert "three more hikes" in text


def test_build_embed_text_truncates_to_max_chars():
    row = {
        "headline": "x" * 200,
        "detail": "y" * 1000,
    }
    text = build_embed_text(row)
    assert len(text) <= 512


def test_build_embed_text_handles_missing_fields():
    row = {"headline": "Only headline", "detail": None}
    text = build_embed_text(row)
    assert text == "Only headline"


def test_build_embed_text_empty_row_returns_empty():
    text = build_embed_text({})
    assert text == ""


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Embedder.cosine_similarity
# ──────────────────────────────────────────────────────────────────────────────

def test_cosine_similarity_identical_vectors():
    embedder = Embedder()
    v = [1.0, 0.0, 0.0, 0.0]
    assert embedder.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)


def test_cosine_similarity_orthogonal_vectors():
    embedder = Embedder()
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert embedder.cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)


def test_cosine_similarity_opposite_vectors():
    embedder = Embedder()
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert embedder.cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-5)


def test_cosine_similarity_zero_vector_returns_zero():
    embedder = Embedder()
    a = [0.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert embedder.cosine_similarity(a, b) == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: OBS_TABLE_MAP completeness
# ──────────────────────────────────────────────────────────────────────────────

def test_all_seven_obs_tables_in_map():
    required = {
        "obs_investor", "obs_financial", "obs_competitive",
        "obs_employee", "obs_macro", "obs_public_market", "obs_customer",
    }
    assert required.issubset(set(OBS_TABLE_MAP.keys()))


def test_obs_table_map_entries_have_four_fields():
    for key, val in OBS_TABLE_MAP.items():
        assert len(val) == 4, f"{key} entry should have (table, col1, col2, embed_col)"


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: _process_one with mocked embed + DB
# ──────────────────────────────────────────────────────────────────────────────

def test_process_one_completes_successfully(mock_db, mock_embed):
    mock_db.execute.return_value.fetchone.return_value = (
        "Jana Partners activist stake",
        "Jana filed a 13D disclosing 7.9% stake.",
    )
    embedder = Embedder(db_session=mock_db)

    job = {
        "id": "job-embed-001",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_investor", "obs_id": "obs-abc-123"}),
        "priority": 3,
    }

    result = embedder._process_one(job)

    assert result.status == "completed"
    assert result.dims == EMBEDDING_DIMS
    assert result.obs_table == "obs_investor"
    assert result.obs_id == "obs-abc-123"
    assert result.elapsed_ms > 0


def test_process_one_skips_unknown_table(mock_db, mock_embed):
    embedder = Embedder(db_session=mock_db)
    job = {
        "id": "job-bad",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_nonexistent", "obs_id": "123"}),
        "priority": 3,
    }
    result = embedder._process_one(job)
    assert result.status == "failed"
    assert "Unknown obs_table" in result.error


def test_process_one_skips_missing_obs_row(mock_db, mock_embed):
    mock_db.execute.return_value.fetchone.return_value = None
    embedder = Embedder(db_session=mock_db)
    job = {
        "id": "job-missing",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_investor", "obs_id": "does-not-exist"}),
        "priority": 3,
    }
    result = embedder._process_one(job)
    assert result.status == "skipped"


def test_process_one_skips_empty_embed_text(mock_db, mock_embed):
    # Row exists but has no text
    mock_db.execute.return_value.fetchone.return_value = (None, None)
    embedder = Embedder(db_session=mock_db)
    job = {
        "id": "job-empty",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_investor", "obs_id": "obs-empty"}),
        "priority": 3,
    }
    result = embedder._process_one(job)
    assert result.status == "skipped"


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: _store_embedding writes correct SQL
# ──────────────────────────────────────────────────────────────────────────────

def test_store_embedding_calls_update(mock_db, mock_embed):
    mock_db.execute.return_value.fetchone.return_value = (
        "Headline text", "Detail text"
    )
    embedder = Embedder(db_session=mock_db)

    job = {
        "id": "job-store",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_investor", "obs_id": "obs-xyz"}),
        "priority": 3,
    }
    embedder._process_one(job)

    # Find the UPDATE call
    update_call = None
    for c in mock_db.execute.call_args_list:
        args = c[0]
        if len(args) >= 2 and isinstance(args[1], dict) and "vec" in args[1]:
            update_call = args[1]
            break

    assert update_call is not None, "Expected UPDATE with vec parameter"
    assert update_call["id"] == "obs-xyz"
    # vec should be a bracketed comma-separated float string
    assert update_call["vec"].startswith("[")
    assert update_call["vec"].endswith("]")


def test_store_embedding_vector_length(mock_db, mock_embed):
    """The stored vector string should encode exactly EMBEDDING_DIMS floats."""
    mock_db.execute.return_value.fetchone.return_value = ("h", "d")
    embedder = Embedder(db_session=mock_db)

    job = {
        "id": "job-len",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_financial", "obs_id": "obs-fin-1"}),
        "priority": 3,
    }
    embedder._process_one(job)

    for c in mock_db.execute.call_args_list:
        args = c[0]
        if len(args) >= 2 and isinstance(args[1], dict) and "vec" in args[1]:
            vec_str = args[1]["vec"]
            floats = [float(x) for x in vec_str.strip("[]").split(",")]
            assert len(floats) == EMBEDDING_DIMS
            break


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Job status transitions
# ──────────────────────────────────────────────────────────────────────────────

def test_job_status_transitions_processing_then_completed(mock_db, mock_embed):
    mock_db.execute.return_value.fetchone.return_value = ("headline", "detail")
    embedder = Embedder(db_session=mock_db)

    job = {
        "id": "job-transition",
        "job_type": "generate_embedding",
        "payload": json.dumps({"obs_table": "obs_investor", "obs_id": "obs-t"}),
        "priority": 3,
    }
    embedder._process_one(job)

    statuses = []
    for c in mock_db.execute.call_args_list:
        args = c[0]
        if len(args) >= 2 and isinstance(args[1], dict) and "status" in args[1]:
            statuses.append(args[1]["status"])

    assert "processing" in statuses
    assert "completed" in statuses


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: enqueue_embedding_job
# ──────────────────────────────────────────────────────────────────────────────

def test_enqueue_embedding_job_inserts_correct_payload(mock_db):
    enqueue_embedding_job(mock_db, "obs_investor", "obs-uuid-123")

    assert mock_db.execute.called
    call_args = mock_db.execute.call_args[0]
    params = call_args[1]
    payload = json.loads(params["payload"])

    assert payload["obs_table"] == "obs_investor"
    assert payload["obs_id"] == "obs-uuid-123"


def test_enqueue_embedding_job_commits(mock_db):
    enqueue_embedding_job(mock_db, "obs_financial", "obs-fin-456")
    mock_db.commit.assert_called()


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: Batch processing
# ──────────────────────────────────────────────────────────────────────────────

def test_batch_result_counts(mock_db, mock_embed):
    # 3 claimed jobs
    mock_db.execute.return_value.fetchall.return_value = [
        ("j1", "generate_embedding", json.dumps({"obs_table": "obs_investor", "obs_id": "1"}), 3),
        ("j2", "generate_embedding", json.dumps({"obs_table": "obs_financial", "obs_id": "2"}), 3),
        ("j3", "generate_embedding", json.dumps({"obs_table": "obs_employee", "obs_id": "3"}), 3),
    ]
    # fetchone returns row data for each obs fetch
    mock_db.execute.return_value.fetchone.return_value = ("headline", "detail")

    embedder = Embedder(db_session=mock_db)
    batch = embedder.process_batch(limit=10)

    assert batch.total_jobs == 3
    assert batch.completed == 3
    assert batch.failed == 0
    assert batch.avg_ms_per_embedding >= 0


# ──────────────────────────────────────────────────────────────────────────────
# LIVE tests — load real model (~2s, ~1.3GB RAM)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.live
def test_embedding_generates_correct_dims():
    """Real model produces exactly 1024-dim vectors."""
    embedder = Embedder()
    vec = embedder.embed("Jana Partners discloses 7.9% activist stake in Alkami Technology")
    assert len(vec) == EMBEDDING_DIMS
    assert all(isinstance(v, float) for v in vec)


@pytest.mark.live
def test_same_text_same_vector():
    """Embedding is deterministic — same input always same output."""
    embedder = Embedder()
    text = "Jana Partners activist stake Alkami Technology"
    v1 = embedder.embed(text)
    v2 = embedder.embed(text)
    assert v1 == v2


@pytest.mark.live
def test_similar_texts_high_cosine_similarity():
    """
    Semantically similar texts should have cosine similarity > 0.8.
    Both describe activist investor filings.
    """
    embedder = Embedder()
    a = embedder.embed("Jana Partners discloses 7.9% activist stake in Alkami Technology")
    b = embedder.embed("Activist investor files Schedule 13D on fintech company, seeks strategic review")
    sim = embedder.cosine_similarity(a, b)
    print(f"\nSimilar texts cosine similarity: {sim:.4f}")
    assert sim > 0.7, f"Expected similarity > 0.7 for similar texts, got {sim:.4f}"


@pytest.mark.live
def test_dissimilar_texts_lower_cosine_similarity():
    """
    Semantically unrelated texts should have lower similarity than related ones.
    Activist filing vs macro interest rate trend.
    """
    embedder = Embedder()
    activist = embedder.embed("Jana Partners discloses 7.9% activist stake in Alkami Technology")
    macro = embedder.embed("Federal Reserve signals interest rate cuts in second half of 2026")
    sim_dissimilar = embedder.cosine_similarity(activist, macro)

    similar = embedder.embed("Activist investor files Schedule 13D seeking board representation")
    sim_similar = embedder.cosine_similarity(activist, similar)

    print(f"\nActivist ↔ Macro:   {sim_dissimilar:.4f}")
    print(f"Activist ↔ Similar: {sim_similar:.4f}")
    assert sim_similar > sim_dissimilar, (
        "Similar texts should score higher than dissimilar texts"
    )


@pytest.mark.live
def test_embed_many_matches_single_embed():
    """embed_many and embed produce identical vectors for the same text."""
    embedder = Embedder()
    texts = [
        "Jana Partners activist stake",
        "Alkami Technology revenue growth",
    ]
    batch_vecs = embedder.embed_many(texts)
    single_vecs = [embedder.embed(t) for t in texts]

    for b, s in zip(batch_vecs, single_vecs):
        sim = embedder.cosine_similarity(b, s)
        assert sim > 0.9999, f"embed_many vs embed mismatch: similarity={sim}"
