"""
Fetch recent news headlines for a stock ticker.

Uses RSS feeds (feedparser) as the primary source — more stable and polite
than scraping HTML pages — with an optional Yahoo Finance HTML fallback
(BeautifulSoup) when RSS returns nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable, List, Optional
from urllib.parse import quote_plus, urlparse
import time

import feedparser
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 12
DEFAULT_LIMIT = 15


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str = ""
    published: Optional[datetime] = None
    summary: str = ""
    provider: str = ""  # e.g. "google_news", "yahoo_rss", "yahoo_html"

    def published_label(self) -> str:
        if not self.published:
            return ""
        local = self.published.astimezone() if self.published.tzinfo else self.published
        return local.strftime("%b %d, %Y  %I:%M %p")


@dataclass
class NewsFetchResult:
    symbol: str
    articles: List[NewsArticle] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def _parse_published(entry) -> Optional[datetime]:
    if getattr(entry, "published_parsed", None):
        try:
            return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
        except (OverflowError, ValueError, OSError):
            pass
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError, IndexError):
        return None


def _entry_source(entry, fallback: str = "") -> str:
    source = getattr(entry, "source", None)
    if isinstance(source, dict) and source.get("title"):
        return str(source["title"]).strip()
    if hasattr(source, "get") and source.get("title"):
        return str(source.get("title")).strip()
    title = getattr(source, "title", None) if source is not None else None
    if title:
        return str(title).strip()
    # Google News often puts publisher in author / tags
    author = getattr(entry, "author", None)
    if author:
        return str(author).strip()
    return fallback


def _clean_html(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def _host_label(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _dedupe(articles: Iterable[NewsArticle]) -> List[NewsArticle]:
    seen = set()
    out: List[NewsArticle] = []
    for article in articles:
        key = (article.title.strip().lower(), article.link.strip().lower())
        if not article.title.strip() or key in seen:
            continue
        seen.add(key)
        out.append(article)
    return out


def _fetch_feed(session: requests.Session, url: str) -> feedparser.FeedParserDict:
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def fetch_google_news_rss(symbol: str, company_name: str = "", limit: int = DEFAULT_LIMIT) -> List[NewsArticle]:
    """Google News RSS search — primary source for ticker-relevant headlines."""
    symbol = symbol.upper().strip()
    short_name = company_name.split(",")[0].strip() if company_name else ""
    if short_name and short_name.upper() != symbol:
        query = f'{symbol} OR "{short_name}" stock'
    else:
        query = f"{symbol} stock"

    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    session = _session()
    feed = _fetch_feed(session, url)
    articles: List[NewsArticle] = []
    for entry in feed.entries[: limit * 2]:
        title = (getattr(entry, "title", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        if not title or not link:
            continue
        articles.append(
            NewsArticle(
                title=title,
                link=link,
                source=_entry_source(entry, fallback="Google News"),
                published=_parse_published(entry),
                summary=_clean_html(getattr(entry, "summary", "") or ""),
                provider="google_news",
            )
        )
    return _dedupe(articles)[:limit]


def fetch_yahoo_finance_rss(symbol: str, limit: int = DEFAULT_LIMIT) -> List[NewsArticle]:
    """Yahoo Finance headline RSS (can be flaky; used as secondary source)."""
    symbol = symbol.upper().strip()
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={quote_plus(symbol)}&region=US&lang=en-US"
    )
    session = _session()
    feed = _fetch_feed(session, url)
    articles: List[NewsArticle] = []
    for entry in feed.entries[: limit * 2]:
        title = (getattr(entry, "title", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        if not title or not link:
            continue
        articles.append(
            NewsArticle(
                title=title,
                link=link,
                source=_entry_source(entry, fallback="Yahoo Finance"),
                published=_parse_published(entry),
                summary=_clean_html(getattr(entry, "summary", "") or ""),
                provider="yahoo_rss",
            )
        )
    return _dedupe(articles)[:limit]


def fetch_yahoo_finance_html(symbol: str, limit: int = DEFAULT_LIMIT) -> List[NewsArticle]:
    """HTML scrape of Yahoo Finance quote news as a last-resort fallback."""
    symbol = symbol.upper().strip()
    url = f"https://finance.yahoo.com/quote/{quote_plus(symbol)}/news"
    session = _session()
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles: List[NewsArticle] = []
    # Yahoo markup changes often; cast a wide net for news-like anchors.
    for a in soup.select('a[href*="/news/"], a[href*="/m/"]'):
        title = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        if not title or len(title) < 25:
            continue
        if href.startswith("/"):
            href = "https://finance.yahoo.com" + href
        if not href.startswith("http"):
            continue
        articles.append(
            NewsArticle(
                title=title,
                link=href,
                source=_host_label(href) or "Yahoo Finance",
                published=None,
                summary="",
                provider="yahoo_html",
            )
        )
        if len(articles) >= limit * 3:
            break
    return _dedupe(articles)[:limit]


def fetch_stock_news(
    symbol: str,
    *,
    company_name: str = "",
    limit: int = DEFAULT_LIMIT,
    use_yahoo_rss: bool = True,
    use_yahoo_html_fallback: bool = True,
) -> NewsFetchResult:
    """
    Aggregate ticker news from available sources.

    Prefer RSS (Google News, Yahoo). Only HTML-scrape Yahoo if feeds fail.
    """
    symbol = (symbol or "").upper().strip()
    result = NewsFetchResult(symbol=symbol)
    if not symbol:
        result.errors.append("Symbol is required.")
        return result

    collected: List[NewsArticle] = []

    try:
        collected.extend(fetch_google_news_rss(symbol, company_name=company_name, limit=limit))
    except Exception as exc:
        result.errors.append(f"Google News RSS: {exc}")

    if use_yahoo_rss:
        try:
            collected.extend(fetch_yahoo_finance_rss(symbol, limit=limit))
        except Exception as exc:
            result.errors.append(f"Yahoo Finance RSS: {exc}")

    if len(_dedupe(collected)) < max(3, limit // 3) and use_yahoo_html_fallback:
        try:
            collected.extend(fetch_yahoo_finance_html(symbol, limit=limit))
        except Exception as exc:
            result.errors.append(f"Yahoo Finance HTML: {exc}")

    merged = _dedupe(collected)
    # Undated articles (common from Google News / HTML) should not sink to the bottom.
    # Stable sort: prefer Google among equal timestamps, then newest first.
    provider_rank = {"google_news": 0, "yahoo_rss": 1, "yahoo_html": 2}
    fallback_ts = result.fetched_at
    merged.sort(key=lambda a: provider_rank.get(a.provider, 9))
    merged.sort(key=lambda a: a.published or fallback_ts, reverse=True)
    result.articles = merged[:limit]
    if not result.articles and not result.errors:
        result.errors.append("No articles found.")
    return result
