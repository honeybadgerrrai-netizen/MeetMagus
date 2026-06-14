"""
app/workers/embedder.py
Embedding background job — generates semantic vectors for observations.

Model: BAAI/bge-large-en-v1.5 (local, free, no API, 1024 dims)
Install: pip install sentence-transformers

The model loads ONCE on startup (~2s, ~1.3GB RAM). All subsequent
embedding calls run in milliseconds on CPU.

What gets embedded:
  Each observation row has a text representation built from its
  headline + detail. The 1024-dim vector is stored in the embedding
  column (pgvector) for semantic search at query time.

Pipeline per job:
  1. Claim "generate_embedding" job from platform.job_queue
  2. Fetch the observation row (obs_investor, obs_financial, etc.)
  3. Build embed_text = headline + ". " + detail
  4. Generate 1024-dim vector
  5. UPDATE observation SET embedding = vector WHERE id = obs_id
  6. Mark job "completed"

Usage:
  # Process all pending embedding jobs once:
  python -m app.workers.embedder

  # Daemon mode:
  python -m app.workers.embedder --daemon --poll-seconds 60

  # Benchmark / smoke test (no DB needed):
  python -m app.workers.embedder --benchmark
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMS = 1024
MAX_TEXT_CHARS = 512  # bge-large handles ~512 tokens; we cap input chars

# Map obs table name → (table, headline_col, detail_col, embedding_col)
OBS_TABLE_MAP = {
    "obs_investor":     ("global.obs_investor",    "headline", "detail", "embedding"),
    "obs_financial":    ("global.obs_financial",   "headline", "detail", "embedding"),
    "obs_competitive":  ("global.obs_competitive", "headline", "detail", "embedding"),
    "obs_employee":     ("global.obs_employee",    "headline", "detail", "embedding"),
    "obs_macro":        ("global.obs_macro",       "trend_name", "trend_description", "embedding"),
    "obs_public_market":("global.obs_public_market","headline", "detail", "embedding"),
    "obs_customer":     ("global.obs_customer",    "headline", "detail", "embedding"),
}

# ──────────────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class EmbedResult:
    job_id: str
    obs_table: str
    obs_id: str
    status: str          # "completed" | "failed" | "skipped"
    dims: int = 0
    embed_text: str = ""
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class EmbedBatchResult:
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    total_elapsed_ms: float = 0.0
    results: list[EmbedResult] = field(default_factory=list)

    @property
    def avg_ms_per_embedding(self) -> float:
        if self.completed == 0:
            return 0.0
        return self.total_elapsed_ms / self.completed


# ──────────────────────────────────────────────────────────────────────────────
# Model loader — singleton, loads once
# ──────────────────────────────────────────────────────────────────────────────

_model_instance = None


def get_model(device: str = "cpu"):
    """
    Load the sentence-transformer model once and cache it.
    Subsequent calls return the cached instance instantly.
    """
    global _model_instance
    if _model_instance is None:
        logger.info("Loading embedding model %s on %s...", EMBEDDING_MODEL, device)
        t0 = time.monotonic()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        _model_instance = SentenceTransformer(EMBEDDING_MODEL, device=device)
        elapsed = time.monotonic() - t0
        logger.info("Model loaded in %.1fs", elapsed)
    return _model_instance


def embed_texts(texts: list[str], device: str = "cpu") -> np.ndarray:
    """
    Generate embeddings for a list of texts.
    Returns float32 numpy array of shape (len(texts), EMBEDDING_DIMS).
    """
    model = get_model(device=device)
    # bge models expect a query prefix for retrieval tasks
    prefixed = [f"Represent this sentence: {t}" for t in texts]
    vecs = model.encode(
        prefixed,
        normalize_embeddings=True,   # L2-normalize for cosine similarity
        batch_size=32,
        show_progress_bar=False,
    )
    return np.array(vecs, dtype=np.float32)


def embed_text(text: str, device: str = "cpu") -> list[float]:
    """Embed a single text. Returns a plain Python list of floats."""
    vecs = embed_texts([text], device=device)
    return vecs[0].tolist()


# ──────────────────────────────────────────────────────────────────────────────
# Text builder — what to embed for each observation
# ──────────────────────────────────────────────────────────────────────────────

def build_embed_text(row: dict) -> str:
    """
    Build the text to embed from an observation row.
    Combines headline + detail, truncated to MAX_TEXT_CHARS.
    """
    parts = []
    for col in ("headline", "trend_name", "detail", "trend_description"):
        val = row.get(col)
        if val and isinstance(val, str):
            parts.append(val.strip())

    text = ". ".join(p for p in parts if p)
    return text[:MAX_TEXT_CHARS]


# ──────────────────────────────────────────────────────────────────────────────
# Embedder worker
# ──────────────────────────────────────────────────────────────────────────────

class Embedder:
    """
    Processes pending generate_embedding jobs from platform.job_queue.

    Usage without DB (benchmark):
        embedder = Embedder(db_session=None)
        vec = embedder.embed("Jana Partners discloses 7.9% activist stake")

    Usage with DB:
        embedder = Embedder(db_session=session)
        batch = embedder.process_batch(limit=100)
    """

    def __init__(self, db_session=None, device: str = "cpu"):
        self._db = db_session
        self._device = device

    def embed(self, text: str) -> list[float]:
        """Embed a single text string. No DB required."""
        return embed_text(text, device=self._device)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one batch. More efficient than calling embed() in a loop."""
        vecs = embed_texts(texts, device=self._device)
        return vecs.tolist()

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Cosine similarity between two embedding vectors."""
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom == 0:
            return 0.0
        return float(np.dot(va, vb) / denom)

    def process_batch(self, limit: int = 100) -> EmbedBatchResult:
        """Claim and process up to `limit` pending generate_embedding jobs."""
        batch = EmbedBatchResult()
        jobs = self._claim_jobs(limit)
        batch.total_jobs = len(jobs)

        for job in jobs:
            result = self._process_one(job)
            batch.results.append(result)
            batch.total_elapsed_ms += result.elapsed_ms
            if result.status == "completed":
                batch.completed += 1
            elif result.status == "failed":
                batch.failed += 1
            else:
                batch.skipped += 1

        return batch

    # ── Internal ──────────────────────────────────────────────────────────────

    def _process_one(self, job: dict) -> EmbedResult:
        job_id = str(job.get("id", ""))
        payload = job.get("payload", {})
        if isinstance(payload, str):
            payload = json.loads(payload)

        obs_table = payload.get("obs_table", "")
        obs_id = str(payload.get("obs_id", ""))

        if obs_table not in OBS_TABLE_MAP:
            self._update_job_status(job_id, "failed", error=f"Unknown obs_table: {obs_table}")
            return EmbedResult(
                job_id=job_id, obs_table=obs_table, obs_id=obs_id,
                status="failed", error=f"Unknown obs_table: {obs_table}"
            )

        self._update_job_status(job_id, "processing")

        try:
            t0 = time.monotonic()

            # Fetch the observation row
            row = self._fetch_obs_row(obs_table, obs_id)
            if not row:
                self._update_job_status(job_id, "skipped")
                return EmbedResult(
                    job_id=job_id, obs_table=obs_table, obs_id=obs_id,
                    status="skipped", error="Observation row not found"
                )

            embed_text_str = build_embed_text(row)
            if not embed_text_str.strip():
                self._update_job_status(job_id, "skipped")
                return EmbedResult(
                    job_id=job_id, obs_table=obs_table, obs_id=obs_id,
                    status="skipped", error="No text to embed"
                )

            vector = self.embed(embed_text_str)
            elapsed_ms = (time.monotonic() - t0) * 1000

            self._store_embedding(obs_table, obs_id, vector)
            self._update_job_status(job_id, "completed")

            logger.debug(
                "Embedded %s/%s in %.1fms (%d dims)",
                obs_table, obs_id, elapsed_ms, len(vector)
            )

            return EmbedResult(
                job_id=job_id,
                obs_table=obs_table,
                obs_id=obs_id,
                status="completed",
                dims=len(vector),
                embed_text=embed_text_str,
                elapsed_ms=elapsed_ms,
            )

        except Exception as e:
            logger.error("Embedding failed for job %s: %s", job_id, e, exc_info=True)
            self._update_job_status(job_id, "failed", error=str(e))
            return EmbedResult(
                job_id=job_id, obs_table=obs_table, obs_id=obs_id,
                status="failed", error=str(e)
            )

    def _fetch_obs_row(self, obs_table: str, obs_id: str) -> dict | None:
        if not self._db:
            return None
        table_def = OBS_TABLE_MAP[obs_table]
        table_name, col1, col2, _ = table_def
        from sqlalchemy import text
        row = self._db.execute(
            text(f"SELECT {col1}, {col2} FROM {table_name} WHERE id = :id LIMIT 1"),
            {"id": obs_id},
        ).fetchone()
        if not row:
            return None
        return {col1: row[0], col2: row[1]}

    def _store_embedding(self, obs_table: str, obs_id: str, vector: list[float]) -> None:
        if not self._db:
            return
        table_def = OBS_TABLE_MAP[obs_table]
        table_name, _, _, embed_col = table_def
        from sqlalchemy import text
        # pgvector accepts Python list via cast
        vec_str = "[" + ",".join(str(v) for v in vector) + "]"
        self._db.execute(
            text(f"""
                UPDATE {table_name}
                SET {embed_col} = :vec::vector
                WHERE id = :id
            """),
            {"vec": vec_str, "id": obs_id},
        )
        self._db.commit()

    def _claim_jobs(self, limit: int) -> list[dict]:
        if not self._db:
            return []
        from sqlalchemy import text
        rows = self._db.execute(
            text("""
                UPDATE platform.job_queue
                SET status = 'claimed', updated_at = NOW()
                WHERE id IN (
                    SELECT id FROM platform.job_queue
                    WHERE job_type = 'generate_embedding'
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

    def _update_job_status(self, job_id: str, status: str, error: str = "") -> None:
        if not self._db:
            return
        from sqlalchemy import text
        self._db.execute(
            text("""
                UPDATE platform.job_queue
                SET status = :status,
                    updated_at = NOW(),
                    error_detail = CASE WHEN :error != '' THEN :error ELSE error_detail END
                WHERE id = :job_id
            """),
            {"status": status, "error": error, "job_id": job_id},
        )
        self._db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Utility: enqueue an embedding job after extraction writes an obs row
# ──────────────────────────────────────────────────────────────────────────────

def enqueue_embedding_job(db_session, obs_table: str, obs_id: str) -> None:
    """
    Called by the extractor after writing an observation row.
    Adds a generate_embedding job to job_queue at priority 3.
    """
    from sqlalchemy import text
    db_session.execute(
        text("""
            INSERT INTO platform.job_queue
                (job_type, priority, payload, status, attempts)
            VALUES
                ('generate_embedding', 3, :payload::jsonb, 'pending', 0)
        """),
        {"payload": json.dumps({"obs_table": obs_table, "obs_id": str(obs_id)})},
    )
    db_session.commit()


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

    parser = argparse.ArgumentParser(description="MeetMagus embedding worker")
    parser.add_argument("--benchmark", action="store_true",
                        help="Benchmark model speed with sample texts (no DB)")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--device", default="cpu", help="cpu or cuda")
    args = parser.parse_args()

    if args.benchmark:
        print(f"\n{'='*60}")
        print(f"MeetMagus Embedder — Benchmark ({EMBEDDING_MODEL})")
        print(f"{'='*60}\n")

        sample_texts = [
            "Jana Partners discloses 7.9% activist stake in Alkami Technology, pushes for sale",
            "General Atlantic holds 18% passive stake in Alkami Technology as strategic investor",
            "Alkami Technology reports Q1 2026 revenue of $91.3M, up 26% year-over-year",
            "MANTL raises Series C funding, expands digital banking platform competition",
            "David Handler advised on Qualcomm defense against Broadcom hostile takeover bid",
        ]

        embedder = Embedder(device=args.device)

        print("Warming up model...")
        _ = embedder.embed("warmup")

        print(f"\nEmbedding {len(sample_texts)} texts...\n")
        t0 = time.monotonic()
        vecs = embedder.embed_many(sample_texts)
        elapsed = (time.monotonic() - t0) * 1000

        print(f"✓ {len(vecs)} embeddings in {elapsed:.1f}ms ({elapsed/len(vecs):.1f}ms each)")
        print(f"✓ Dimensions: {len(vecs[0])}")
        print(f"\nSimilarity matrix (cosine):")
        labels = [t[:45] + "..." for t in sample_texts]
        for i, (vi, li) in enumerate(zip(vecs, labels)):
            for j, (vj, lj) in enumerate(zip(vecs, labels)):
                if j > i:
                    sim = embedder.cosine_similarity(vi, vj)
                    print(f"  [{i}]↔[{j}] {sim:.3f}  {li[:30]} ↔ {lj[:30]}")

    elif args.daemon:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise SystemExit("DATABASE_URL not set")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        engine = create_engine(db_url)
        embedder = Embedder(device=args.device)
        # Pre-load model before entering loop
        embedder.embed("warmup")
        print(f"Daemon ready — polling every {args.poll_seconds}s")
        while True:
            with Session(engine) as session:
                embedder._db = session
                batch = embedder.process_batch(limit=args.limit)
                if batch.total_jobs > 0:
                    print(
                        f"Batch: {batch.total_jobs} jobs — "
                        f"{batch.completed} embedded "
                        f"(avg {batch.avg_ms_per_embedding:.1f}ms), "
                        f"{batch.failed} failed"
                    )
            time.sleep(args.poll_seconds)

    else:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise SystemExit("DATABASE_URL not set. Use --benchmark for no-DB mode.")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        engine = create_engine(db_url)
        with Session(engine) as session:
            embedder = Embedder(db_session=session, device=args.device)
            batch = embedder.process_batch(limit=args.limit)
        print(
            f"Done: {batch.completed} embedded, {batch.failed} failed, "
            f"{batch.skipped} skipped"
        )
