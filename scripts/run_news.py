"""
scripts/run_news.py
Functional test + production runner for the news signal pipeline.

DRY RUN (no DB, no API key needed for fetching):
    python -m scripts.run_news --company "Infoblox" --dry-run
    python -m scripts.run_news --company "Alkami Technology" --dry-run --days 14

    Output: every article → what obs_type → what fields → which table it would write to.
    Requires GROQ_API_KEY for LLM classification.

LIVE MODE (writes to DB):
    DATABASE_URL="..." python -m scripts.run_news --company "Infoblox"
    DATABASE_URL="..." python -m scripts.run_news --all-companies

FETCH ONLY (no LLM, just show raw articles):
    python -m scripts.run_news --company "Infoblox" --fetch-only

Environment:
    GROQ_API_KEY    Required for LLM classification (not needed for --fetch-only)
    DATABASE_URL    Required for live mode (not needed for --dry-run)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.fetchers.news import NewsFetcher, NewsArticle
from app.workers.prompts.news import build_news_extraction_messages
from app.workers.extractor import parse_llm_json

logging.basicConfig(
    level=logging.WARNING,  # suppress INFO noise during dry-run
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("run_news")

# ── Table routing ──────────────────────────────────────────────────────────────

OBS_TABLE_MAP = {
    "financial":   "global.obs_financial",
    "competitive": "global.obs_competitive",
    "customer":    "global.obs_customer",
    "org_event":   "global.obs_org_events",
    "investor":    "global.obs_investor",
    "macro":       "global.obs_macro",
    "regulatory":  "global.obs_regulatory",
    "clinical":    "global.obs_clinical",
    "irrelevant":  "(discarded — not written)",
}

OBS_TYPE_EMOJI = {
    "financial":   "💰",
    "competitive": "⚔️ ",
    "customer":    "🤝",
    "org_event":   "👤",
    "investor":    "📈",
    "macro":       "🌍",
    "regulatory":  "🏛️ ",
    "clinical":    "🧪",
    "irrelevant":  "🗑️ ",
}


# ── LLM classification ─────────────────────────────────────────────────────────

def classify_article(article: NewsArticle) -> dict | None:
    """
    Call the LLM to classify one article and extract structured fields.
    Returns parsed JSON dict, or None on failure.
    """
    from app.core.llm import LLMClient

    messages = build_news_extraction_messages(
        company_name=article.company_name,
        headline=article.headline,
        summary=article.summary,
        source=article.source,
        published_date=article.published_at.strftime("%Y-%m-%d"),
    )

    try:
        client = LLMClient()
        response = client.complete(
            task="news_extraction",
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return parse_llm_json(raw)
    except Exception as exc:
        logger.error("LLM classification failed: %s", exc)
        return None


# ── Dry-run output ─────────────────────────────────────────────────────────────

def print_article_result(i: int, article: NewsArticle, extracted: dict | None) -> None:
    """Print one article's classification result in a readable format."""

    print(f"\n{'─'*65}")
    print(f"[{i}] {article.headline}")
    print(f"     {article.source}  |  {article.published_at.strftime('%Y-%m-%d')}")
    print(f"     {article.url[:80]}{'...' if len(article.url) > 80 else ''}")

    if extracted is None:
        print(f"\n     ⚠️  LLM classification failed")
        return

    obs_type   = extracted.get("obs_type", "irrelevant")
    signal_type = extracted.get("signal_type", "")
    headline   = extracted.get("headline", "")
    detail     = extracted.get("detail", "")
    confidence = extracted.get("confidence", 0.0)
    is_subject = extracted.get("is_about_subject_company", True)
    table      = OBS_TABLE_MAP.get(obs_type, "(unknown)")
    emoji      = OBS_TYPE_EMOJI.get(obs_type, "  ")

    print(f"\n     {emoji} obs_type   : {obs_type.upper()}")
    print(f"        signal     : {signal_type}")
    print(f"        confidence : {confidence:.0%}")
    print(f"        is_subject : {is_subject}")
    print(f"        headline   : {headline}")
    if detail:
        # Wrap detail at 60 chars
        words = detail.split()
        lines, line = [], []
        for word in words:
            line.append(word)
            if len(" ".join(line)) > 58:
                lines.append(" ".join(line[:-1]))
                line = [word]
        if line:
            lines.append(" ".join(line))
        print(f"        detail     : {lines[0]}")
        for l in lines[1:]:
            print(f"                     {l}")

    # Print type-specific extracted fields
    type_data = extracted.get(obs_type, {}) or {}
    if type_data and obs_type != "irrelevant":
        print(f"        fields     :", end="")
        first = True
        for k, v in type_data.items():
            if v is not None and v != "" and k != "signal_type":
                prefix = " " if first else "                     "
                print(f"{prefix}{k} = {v}")
                first = False

    print(f"\n     → Would write to: {table}")


def print_summary(company: str, results: list[tuple[NewsArticle, dict | None]]) -> None:
    """Print a summary table at the end."""
    from collections import Counter
    counts = Counter()
    for _, extracted in results:
        if extracted:
            counts[extracted.get("obs_type", "irrelevant")] += 1
        else:
            counts["error"] += 1

    print(f"\n{'='*65}")
    print(f"  SUMMARY — {company}")
    print(f"{'='*65}")
    total = len(results)
    for obs_type, count in sorted(counts.items(), key=lambda x: -x[1]):
        table = OBS_TABLE_MAP.get(obs_type, "(unknown)")
        emoji = OBS_TYPE_EMOJI.get(obs_type, "  ")
        bar = "█" * count
        print(f"  {emoji} {obs_type:<12} {count:>3}  {bar}  → {table}")
    print(f"{'─'*65}")
    print(f"  Total articles classified: {total}")
    written = sum(1 for _, e in results if e and e.get("obs_type") != "irrelevant")
    print(f"  Would write to DB:         {written}")
    print(f"  Would discard:             {total - written}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

MOCK_ARTICLES = [
    {
        "headline": "Infoblox wins $47M five-year contract with U.S. Department of Defense for DNS security infrastructure",
        "summary": "Infoblox announced today it has secured a $47 million, five-year contract with the U.S. Department of Defense to provide enterprise DNS, DHCP, and IP address management infrastructure across military networks.",
        "source": "Reuters",
        "published_at": "2026-06-05",
    },
    {
        "headline": "Cisco launches DNS Advantage, entering Infoblox's core market with enterprise DDI platform",
        "summary": "Cisco Systems unveiled DNS Advantage, a new enterprise DNS, DHCP, and IP address management platform targeting the same Fortune 500 customers as Infoblox. The product includes AI-powered threat detection and integrates with Cisco's existing security portfolio.",
        "source": "TechCrunch",
        "published_at": "2026-06-04",
    },
    {
        "headline": "Infoblox CFO Scott Harrell to depart at end of Q2, successor search underway",
        "summary": "Infoblox confirmed that Chief Financial Officer Scott Harrell will leave the company at the end of the second quarter. The board has engaged an executive search firm to identify candidates. Harrell joined in 2021 and oversaw the company's go-private transaction with Vista Equity Partners.",
        "source": "Wall Street Journal",
        "published_at": "2026-06-03",
    },
    {
        "headline": "Infoblox reports ARR growth of 28% year-over-year, raises full-year guidance to $620M",
        "summary": "Infoblox reported annual recurring revenue of $155M for Q2 FY2026, representing 28% year-over-year growth. The company raised its full-year ARR guidance to $620M from $600M, citing strong demand from financial services and government customers.",
        "source": "Bloomberg",
        "published_at": "2026-06-02",
    },
    {
        "headline": "Rising nation-state DNS attacks create tailwind for enterprise DNS security vendors",
        "summary": "A new report from Gartner highlights a 340% increase in DNS-based cyberattacks targeting critical infrastructure in 2025, driven by nation-state actors. Vendors focused on DNS security including Infoblox, Akamai, and Cloudflare are expected to benefit significantly.",
        "source": "Gartner",
        "published_at": "2026-06-01",
    },
    {
        "headline": "Infoblox named a Leader in 2026 Gartner Magic Quadrant for DNS Security",
        "summary": "Gartner has positioned Infoblox as a Leader in its 2026 Magic Quadrant for DNS Security for the fourth consecutive year, citing the company's completeness of vision and ability to execute.",
        "source": "PR Newswire",
        "published_at": "2026-05-31",
    },
    {
        "headline": "Vista Equity Partners hires 12 senior sales engineers from Palo Alto Networks to accelerate Infoblox growth",
        "summary": "Vista Equity Partners has orchestrated a coordinated hire of 12 senior sales engineers from Palo Alto Networks to join Infoblox, signaling an aggressive push into the enterprise security market ahead of a potential IPO.",
        "source": "The Information",
        "published_at": "2026-05-30",
    },
]


def get_mock_articles(company_name: str) -> list[NewsArticle]:
    """Return realistic sample articles for testing LLM classification."""
    from datetime import datetime, timezone
    articles = []
    for i, m in enumerate(MOCK_ARTICLES):
        pub = datetime.strptime(m["published_at"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        import hashlib, json
        url = f"https://mock-news.example.com/article-{i}"
        raw = json.dumps({**m, "url": url, "company_name": company_name})
        articles.append(NewsArticle(
            company_name=company_name,
            headline=m["headline"],
            summary=m["summary"],
            url=url,
            source=m["source"],
            published_at=pub,
            content_hash=hashlib.sha256(url.encode()).hexdigest(),
            raw_text=raw,
        ))
    return articles


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="News signal pipeline — fetch, classify, and show what would be stored",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--company", metavar="NAME",
                        help='Company name to search, e.g. "Infoblox"')
    target.add_argument("--all-companies", action="store_true",
                        help="Fetch for all companies in the DB")

    p.add_argument("--days", type=int, default=7, metavar="N",
                   help="Lookback window in days (default: 7)")
    p.add_argument("--max", type=int, default=20, metavar="N",
                   help="Max articles to process (default: 20)")
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch + classify but do NOT write to DB")
    p.add_argument("--fetch-only", action="store_true",
                   help="Only fetch articles, skip LLM classification")
    p.add_argument("--mock", action="store_true",
                   help="Use built-in sample articles instead of Google News (no network needed). Good for testing LLM classification.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.fetch_only:
        # Just show raw articles, no LLM
        fetcher = NewsFetcher(db_session=None)
        company = args.company or "all companies"
        companies = [args.company] if args.company else []

        print(f"\n{'='*65}")
        print(f"  News Fetch (no classification) — {company}")
        print(f"  Last {args.days} days | max {args.max} articles")
        print(f"{'='*65}")

        for name in companies:
            result = fetcher.fetch_for_company(name, since_days=args.days, max_articles=args.max)
            print(f"\n  {name}: {result.total_found} articles, {result.new_ingestions} in window")
            for a in result.articles:
                print(f"  [{a.source:<20}] {a.published_at.strftime('%Y-%m-%d')}  {a.headline[:65]}")
        return

    # Check for GROQ_API_KEY
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set. LLM classification requires it.")
        print("  export GROQ_API_KEY='gsk_...'")
        sys.exit(1)

    # Dry run or live
    db_session = None
    if not args.dry_run:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("No DATABASE_URL set — running in implicit dry-run mode.")
            args.dry_run = True
        else:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session
            engine = create_engine(db_url)
            db_session = Session(engine)

    fetcher = NewsFetcher(db_session=None)  # always fetch without DB (classify first)

    companies = [args.company] if args.company else []

    for company_name in companies:
        mode_label = "MOCK" if args.mock else ("DRY RUN" if args.dry_run else "LIVE")
        print(f"\n{'='*65}")
        print(f"  News Signal Scan — {company_name}")
        print(f"  Last {args.days} days  |  max {args.max} articles  |  {mode_label}")
        print(f"{'='*65}")

        if args.mock:
            articles = get_mock_articles(company_name)
            print(f"\n  Using {len(articles)} mock articles (no Google News needed)")
        else:
            result = fetcher.fetch_for_company(
                company_name,
                since_days=args.days,
                max_articles=args.max,
            )
            articles = result.articles
            if result.errors:
                for e in result.errors:
                    print(f"  ERROR: {e}")

        if not articles:
            print(f"\n  No articles found in the last {args.days} days.")
            continue

        print(f"\n  Classifying {len(articles)} articles with LLM...\n")

        classified: list[tuple[NewsArticle, dict | None]] = []

        for i, article in enumerate(articles, 1):
            extracted = classify_article(article)
            classified.append((article, extracted))
            print_article_result(i, article, extracted)

            # In live mode, write signals that pass the relevance bar
            if not args.dry_run and db_session and extracted:
                obs_type = extracted.get("obs_type", "irrelevant")
                confidence = extracted.get("confidence", 0.0)
                is_subject = extracted.get("is_about_subject_company", True)

                if obs_type != "irrelevant" and confidence >= 0.6 and is_subject:
                    # TODO: wire to extractor._write_observation() once company_id resolution is in
                    logger.info("Would write %s signal for %s", obs_type, company_name)

        print_summary(company_name, classified)

    if db_session:
        db_session.close()


if __name__ == "__main__":
    main()
