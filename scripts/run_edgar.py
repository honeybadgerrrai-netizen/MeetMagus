"""
scripts/run_edgar.py
Targeted EDGAR fetch runner — fetch for a specific company or across the market.

Unlike run_pipeline.sh (which runs the whole pipeline sequentially),
this script lets you aim at a specific company CIK or pull recent filings
across EDGAR, then optionally run extraction and embedding in the same pass.

Usage examples:

  # Dry run — fetch last 7 days of 13D/13G, no DB writes:
  python -m scripts.run_edgar --dry-run

  # Fetch for Alkami Technology (CIK 1834016), last 30 days:
  DATABASE_URL="..." python -m scripts.run_edgar --cik 1834016 --days 30

  # Broad fetch — all 13D filings from the last 14 days:
  DATABASE_URL="..." python -m scripts.run_edgar --days 14 --forms "SC 13D" "SC 13D/A"

  # Fetch + extract in one go (runs the extractor after fetching):
  DATABASE_URL="..." python -m scripts.run_edgar --cik 1834016 --with-extract

  # Full pipeline for one company (fetch + extract + embed):
  DATABASE_URL="..." python -m scripts.run_edgar --cik 1834016 --with-extract --with-embed

  # Market-wide 8-K sweep, last 2 days:
  DATABASE_URL="..." python -m scripts.run_edgar --days 2 --forms 8-K --with-extract

Environment:
  DATABASE_URL  Postgres connection string (from Railway or .env)
  GROQ_API_KEY  Required if using --with-extract (LLM calls)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta

# Allow running as `python -m scripts.run_edgar` from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.fetchers.edgar import (
    EdgarFetcher,
    FORM_TYPES_ACTIVIST,
    FORM_TYPES_MATERIAL,
    FORM_TYPES_PASSIVE,
    FORM_TYPES_DEFAULT,
    FORM_TYPES_INSIDER,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("run_edgar")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Targeted EDGAR fetch + optional extract/embed pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Target selection
    grp = p.add_mutually_exclusive_group()
    grp.add_argument(
        "--cik",
        metavar="CIK",
        help="Company CIK — fetch filings for this company only (uses submissions API)",
    )
    grp.add_argument(
        "--market",
        action="store_true",
        default=False,
        help="Fetch across all EDGAR filings (uses EFTS search API). Default when --cik not set.",
    )

    # Date range
    p.add_argument(
        "--days",
        type=int,
        default=7,
        metavar="N",
        help="Fetch filings from the last N days (default: 7)",
    )
    p.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Fetch filings since this date (overrides --days)",
    )

    # Form filter
    p.add_argument(
        "--forms",
        nargs="+",
        metavar="FORM",
        help=(
            "Form types to fetch. "
            "Defaults: SC 13D, SC 13D/A, SC 13G, SC 13G/A, 8-K, 8-K/A. "
            "Examples: --forms 'SC 13D' '8-K'  or  --forms activist  or  --forms material"
        ),
    )

    # Pipeline stages
    p.add_argument(
        "--with-extract",
        action="store_true",
        help="After fetching, run the extractor on pending jobs (requires GROQ_API_KEY)",
    )
    p.add_argument(
        "--with-embed",
        action="store_true",
        help="After extraction, run the embedder (requires sentence-transformers)",
    )
    p.add_argument(
        "--extract-limit",
        type=int,
        default=50,
        metavar="N",
        help="Max extraction jobs to process in --with-extract mode (default: 50)",
    )
    p.add_argument(
        "--embed-limit",
        type=int,
        default=100,
        metavar="N",
        help="Max embedding jobs to process in --with-embed mode (default: 100)",
    )

    # Mode flags
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print filings but do not write to DB or call LLM",
    )
    p.add_argument(
        "--max-results",
        type=int,
        default=100,
        metavar="N",
        help="Max filings to fetch in market-wide mode (default: 100)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Show DEBUG logs",
    )

    return p.parse_args()


def resolve_forms(forms_arg: list[str] | None) -> list[str]:
    """Resolve --forms arg to a list of EDGAR form type strings."""
    if not forms_arg:
        return FORM_TYPES_DEFAULT

    # Allow shorthand aliases
    aliases = {
        "activist":  FORM_TYPES_ACTIVIST,
        "passive":   FORM_TYPES_PASSIVE,
        "material":  FORM_TYPES_MATERIAL,
        "insider":   FORM_TYPES_INSIDER,
        "all":       FORM_TYPES_DEFAULT + FORM_TYPES_INSIDER,
    }

    result = []
    for f in forms_arg:
        if f.lower() in aliases:
            result.extend(aliases[f.lower()])
        else:
            result.append(f)
    return list(dict.fromkeys(result))  # deduplicate, preserve order


def resolve_since(args: argparse.Namespace) -> date:
    if args.since:
        try:
            return date.fromisoformat(args.since)
        except ValueError:
            logger.error("Invalid --since date: %r (expected YYYY-MM-DD)", args.since)
            sys.exit(1)
    return date.today() - timedelta(days=args.days)


def get_db_session():
    """Return a SQLAlchemy Session or None if DATABASE_URL not set."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None, None
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    engine = create_engine(db_url)
    session = Session(engine)
    return engine, session


# ──────────────────────────────────────────────────────────────────────────────
# Dry-run output
# ──────────────────────────────────────────────────────────────────────────────

def print_dry_run_results(result) -> None:
    print(f"\n{'─'*70}")
    print(f"DRY RUN — {result.total_found} filing(s) found")
    print(f"{'─'*70}")
    for f in result.filings[:50]:
        print(
            f"  [{f.form_type:10s}] {f.filed_at}  "
            f"{f.company_name[:40]:<40}  "
            f"filer: {f.filer_name[:30]}"
        )
    if not result.filings:
        print("  (no filings matched)")
    if result.errors:
        print(f"\n  Errors ({len(result.errors)}):")
        for e in result.errors[:5]:
            print(f"    {e}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    forms = resolve_forms(args.forms)
    since = resolve_since(args)

    logger.info(
        "EDGAR run | mode=%s | forms=%s | since=%s | dry_run=%s",
        f"cik:{args.cik}" if args.cik else "market",
        forms,
        since,
        args.dry_run,
    )

    # DB session — None if dry run or DATABASE_URL not set
    engine, session = (None, None) if args.dry_run else get_db_session()
    if not args.dry_run and session is None:
        logger.warning(
            "DATABASE_URL not set — running in implicit dry-run mode. "
            "Set DATABASE_URL to write to DB."
        )

    try:
        fetcher = EdgarFetcher(db_session=session)

        # ── Fetch ────────────────────────────────────────────────────────────
        if args.cik:
            logger.info("Fetching for CIK %s since %s", args.cik, since)
            result = fetcher.fetch_for_company(
                cik=args.cik,
                form_types=forms,
                since_days=args.days,
            )
        else:
            logger.info("Market-wide fetch — last %d days, max %d results", args.days, args.max_results)
            result = fetcher.fetch_recent_filings(
                form_types=forms,
                since_date=since,
                max_results=args.max_results,
            )

        fetcher.close()

        # ── Summary ──────────────────────────────────────────────────────────
        if args.dry_run or session is None:
            print_dry_run_results(result)
        else:
            print(f"\n{'─'*50}")
            print(f"Fetch complete")
            print(f"  Found:       {result.total_found}")
            print(f"  New to DB:   {result.new_ingestions}")
            print(f"  Deduped:     {result.skipped_dedup}")
            print(f"  Errors:      {len(result.errors)}")
            if result.errors:
                for e in result.errors[:5]:
                    print(f"    {e}")
            print()

        # ── Optional: Extract ─────────────────────────────────────────────────
        if args.with_extract and not args.dry_run and session is not None:
            logger.info("Running extractor (limit=%d)...", args.extract_limit)
            from app.workers.extractor import Extractor
            extractor = Extractor(db_session=session)
            batch = extractor.process_batch(limit=args.extract_limit)
            print(f"Extract: {batch.completed} completed, {batch.failed} failed, {batch.skipped} skipped")

        # ── Optional: Embed ───────────────────────────────────────────────────
        if args.with_embed and not args.dry_run and session is not None:
            logger.info("Running embedder (limit=%d)...", args.embed_limit)
            from app.workers.embedder import Embedder
            embedder = Embedder(db_session=session)
            batch = embedder.process_batch(limit=args.embed_limit)
            print(
                f"Embed: {batch.completed} embedded "
                f"(avg {batch.avg_ms_per_embedding:.0f}ms), "
                f"{batch.failed} failed"
            )

    finally:
        if session:
            session.close()
        if engine:
            engine.dispose()


if __name__ == "__main__":
    main()
