"""
app/fetchers/news.py
Google News RSS fetcher — collects news signals for tracked companies.

No API key required. Google News RSS is free and public.

Pipeline per company:
  1. Build Google News RSS search URL for the company name
  2. Fetch and parse the RSS feed (headline, summary, source, date, URL)
  3. Level 1 dedup: hash the article URL — skip if already in raw_ingestions
  4. Write raw article to raw_ingestions (extraction_status = "pending")
  5. Enqueue job_queue row (job_type = "extract_news")

Usage:
  # Dry run — fetch and print, no DB writes:
  python -m app.fetchers.news "Infoblox"

  # With DB:
  DATABASE_URL="..." python -m app.fetchers.news "Infoblox"

  # Multiple companies:
  DATABASE_URL="..." python -m app.fetchers.news "Infoblox" "Alkami Technology" "Arista"
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Google News RSS — search by company name, filtered to English/US
GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=en-US&gl=US&ceid=US:en"
)

# Be polite to Google — don't hammer their RSS endpoint
REQUEST_DELAY_SECONDS = 2.0

# Max articles to process per company per run (Google returns ~100)
MAX_ARTICLES_PER_COMPANY = 20

# Only fetch articles from the last N days by default
DEFAULT_LOOKBACK_DAYS = 7

# HTTP headers — identify ourselves
HEADERS = {
    "User-Agent": "MeetMagus/1.0 (Investment Intelligence; contact@meetmagus.ai)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class NewsArticle:
    """A single article from Google News RSS."""
    company_name: str           # the company we searched for
    headline: str               # article title
    summary: str                # article description/snippet
    url: str                    # canonical article URL
    source: str                 # publisher name (Reuters, TechCrunch, etc.)
    published_at: datetime      # publication datetime (UTC)
    content_hash: str           # SHA-256 of the URL (dedup key)
    raw_text: str               # JSON of all fields (stored in raw_ingestions)


@dataclass
class NewsFetchResult:
    """Summary of one fetch run for one company."""
    company_name: str
    since_date: date
    total_found: int = 0
    new_ingestions: int = 0
    skipped_dedup: int = 0
    skipped_old: int = 0
    errors: list[str] = field(default_factory=list)
    articles: list[NewsArticle] = field(default_factory=list)


# ── RSS parser ─────────────────────────────────────────────────────────────────

def _fetch_rss(company_name: str) -> str:
    """Fetch the raw RSS XML for a company name search."""
    query = urllib.parse.quote(f'"{company_name}"')
    url = GOOGLE_NEWS_RSS_URL.format(query=query)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_rss(xml_text: str, company_name: str) -> list[NewsArticle]:
    """Parse RSS XML into a list of NewsArticle objects."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("RSS parse error for %s: %s", company_name, exc)
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    articles = []
    for item in channel.findall("item"):
        title_el    = item.find("title")
        link_el     = item.find("link")
        desc_el     = item.find("description")
        pubdate_el  = item.find("pubDate")
        source_el   = item.find("source")

        headline = (title_el.text or "").strip() if title_el is not None else ""
        url      = (link_el.text or "").strip()  if link_el  is not None else ""
        summary  = (desc_el.text or "").strip()  if desc_el  is not None else ""
        source   = (source_el.text or "").strip() if source_el is not None else "Unknown"

        # Strip HTML tags from summary (Google sometimes includes them)
        import re
        summary = re.sub(r"<[^>]+>", "", summary).strip()

        # Parse publication date
        pub_dt = datetime.now(timezone.utc)
        if pubdate_el is not None and pubdate_el.text:
            try:
                pub_dt = parsedate_to_datetime(pubdate_el.text)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        if not url or not headline:
            continue

        # Hash the URL as the dedup key (not the content — content changes with redirects)
        content_hash = hashlib.sha256(url.encode()).hexdigest()

        raw_payload = {
            "company_name": company_name,
            "headline": headline,
            "summary": summary,
            "url": url,
            "source": source,
            "published_at": pub_dt.isoformat(),
        }

        articles.append(NewsArticle(
            company_name=company_name,
            headline=headline,
            summary=summary,
            url=url,
            source=source,
            published_at=pub_dt,
            content_hash=content_hash,
            raw_text=json.dumps(raw_payload),
        ))

    return articles


# ── Fetcher ────────────────────────────────────────────────────────────────────

class NewsFetcher:
    """
    Fetches Google News RSS for one or more companies.
    Optionally persists to DB (raw_ingestions + job_queue).

    Usage without DB (dry run / testing):
        fetcher = NewsFetcher(db_session=None)
        result = fetcher.fetch_for_company("Infoblox", since_days=7)
        for article in result.articles:
            print(article.headline)

    Usage with DB:
        fetcher = NewsFetcher(db_session=session)
        result = fetcher.fetch_for_company("Infoblox", since_days=1)
    """

    def __init__(self, db_session=None):
        self._db = db_session
        self._last_request_at: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch_for_company(
        self,
        company_name: str,
        since_days: int = DEFAULT_LOOKBACK_DAYS,
        max_articles: int = MAX_ARTICLES_PER_COMPANY,
    ) -> NewsFetchResult:
        """
        Fetch recent news for one company. Returns NewsFetchResult.

        Args:
            company_name: plain English company name (e.g. "Infoblox")
            since_days:   only include articles published in the last N days
            max_articles: cap on articles processed per run
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        since_date = cutoff.date()
        result = NewsFetchResult(company_name=company_name, since_date=since_date)

        logger.info("Fetching news for %r (last %d days)", company_name, since_days)

        # Fetch RSS
        self._throttle()
        try:
            xml_text = _fetch_rss(company_name)
        except Exception as exc:
            msg = f"RSS fetch failed for {company_name!r}: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            return result

        # Parse
        articles = _parse_rss(xml_text, company_name)
        logger.info("Parsed %d articles for %r", len(articles), company_name)

        processed = 0
        for article in articles:
            if processed >= max_articles:
                break

            result.total_found += 1

            # Skip old articles
            if article.published_at < cutoff:
                result.skipped_old += 1
                continue

            # Level 1 dedup: URL hash
            if self._db and self._is_duplicate(article.content_hash):
                result.skipped_dedup += 1
                logger.debug("Skipping duplicate: %s", article.url)
                continue

            result.articles.append(article)

            if self._db:
                try:
                    self._write_raw_ingestion(article)
                    self._enqueue_extraction(article)
                    result.new_ingestions += 1
                except Exception as exc:
                    msg = f"DB write error for {article.url}: {exc}"
                    logger.error(msg)
                    result.errors.append(msg)
            else:
                result.new_ingestions += 1

            processed += 1

        logger.info(
            "%r: %d found, %d new, %d deduped, %d too old, %d errors",
            company_name,
            result.total_found,
            result.new_ingestions,
            result.skipped_dedup,
            result.skipped_old,
            len(result.errors),
        )
        return result

    def fetch_for_companies(
        self,
        company_names: list[str],
        since_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> list[NewsFetchResult]:
        """Fetch news for multiple companies. Throttled between each."""
        results = []
        for name in company_names:
            results.append(self.fetch_for_company(name, since_days=since_days))
        return results

    # ── DB helpers ─────────────────────────────────────────────────────────────

    def _is_duplicate(self, content_hash: str) -> bool:
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

    def _write_raw_ingestion(self, article: NewsArticle) -> None:
        from sqlalchemy import text
        self._db.execute(
            text("""
                INSERT INTO platform.raw_ingestions
                    (source_id, content_hash, raw_content, content_type,
                     extraction_status, metadata, fetched_at)
                VALUES
                    ('google_news', :hash, :content, 'application/json',
                     'pending', :meta::jsonb, NOW())
                ON CONFLICT (content_hash) DO NOTHING
            """),
            {
                "hash":    article.content_hash,
                "content": article.raw_text,
                "meta": json.dumps({
                    "company_name": article.company_name,
                    "headline":     article.headline,
                    "source":       article.source,
                    "url":          article.url,
                    "published_at": article.published_at.isoformat(),
                }),
            },
        )
        self._db.commit()

    def _enqueue_extraction(self, article: NewsArticle) -> None:
        from sqlalchemy import text
        self._db.execute(
            text("""
                INSERT INTO platform.job_queue
                    (job_type, priority, payload, status, attempts)
                VALUES
                    ('extract_news', 2, :payload::jsonb, 'pending', 0)
            """),
            {
                "payload": json.dumps({
                    "source":        "google_news",
                    "company_name":  article.company_name,
                    "headline":      article.headline,
                    "summary":       article.summary,
                    "url":           article.url,
                    "source_name":   article.source,
                    "published_at":  article.published_at.isoformat(),
                    "content_hash":  article.content_hash,
                }),
            },
        )
        self._db.commit()


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    companies = sys.argv[1:] if len(sys.argv) > 1 else ["Infoblox"]
    fetcher = NewsFetcher(db_session=None)

    for company in companies:
        result = fetcher.fetch_for_company(company, since_days=7)
        print(f"\n{'─'*60}")
        print(f"{company}: {result.total_found} articles found, {result.new_ingestions} new")
        print(f"{'─'*60}")
        for a in result.articles[:10]:
            print(f"  [{a.source}] {a.published_at.date()}  {a.headline[:80]}")
