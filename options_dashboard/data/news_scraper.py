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
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote_plus, urlparse
import calendar
import json
import re

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

_VERBOSE_SYMBOLS_PATH = (
    Path(__file__).resolve().parents[1] / "US_stock_symbols_verbose.json"
)
_HISTORY_FILE = Path(__file__).resolve().parents[2] / "ticker_history.json"
_HISTORY_MIN_COUNT = 3
_COMPANY_NAME_CACHE: Dict[str, str] = {}
_HISTORY_COUNT_CACHE: Optional[Dict[str, int]] = None

# Brand / related-ticker overrides for tickers from ticker_history.json (count >= 3).
# Keys use normalized symbols (BRK/B -> BRK.B). Gated by _get_ticker_aliases().
_BRAND_OVERRIDES: Dict[str, Dict[str, List[str]]] = {
    # ETFs & leveraged products
    "SPY": {"brands": ["S&P 500", "S&P"]},
    "QQQ": {"brands": ["Nasdaq 100", "Nasdaq"]},
    "SOXL": {"brands": ["semiconductor", "chip stocks"]},
    "TQQQ": {"tickers": ["QQQ"], "brands": ["Nasdaq", "Nasdaq 100"]},
    "XLV": {"brands": ["healthcare sector", "health care"]},
    # Dual tickers / brand != legal name
    "GOOG": {"tickers": ["GOOGL"], "brands": ["Google", "Alphabet"]},
    "GOOGL": {"tickers": ["GOOG"], "brands": ["Google", "Alphabet"]},
    "META": {"brands": ["Meta", "Facebook"]},
    "FB": {"tickers": ["META"], "brands": ["Meta", "Facebook"]},
    "BRK.A": {"tickers": ["BRK.B"], "brands": ["Berkshire Hathaway", "Berkshire"]},
    "BRK.B": {"tickers": ["BRK.A"], "brands": ["Berkshire Hathaway", "Berkshire"]},
    # Frequently searched stocks (from ticker_history.json)
    "DELL": {"brands": ["Dell"]},
    "AXTI": {"brands": ["AXT"]},
    "NVDA": {"brands": ["Nvidia"]},
    "TSLA": {"brands": ["Tesla"]},
    "MRVL": {"brands": ["Marvell"]},
    "MU": {"brands": ["Micron"]},
    "COHR": {"brands": ["Coherent"]},
    "PANW": {"brands": ["Palo Alto Networks", "Palo Alto"]},
    "PLTR": {"brands": ["Palantir"]},
    "AVGO": {"brands": ["Broadcom"]},
    "LITE": {"brands": ["Lumentum"]},
    "AMD": {"brands": ["Advanced Micro Devices"]},
    "ADBE": {"brands": ["Adobe"]},
    "TGT": {"brands": ["Target"]},
    "BRKR": {"brands": ["Bruker"]},
    "PFE": {"brands": ["Pfizer"]},
    "AAPL": {"brands": ["Apple"]},
    "ORCL": {"brands": ["Oracle"]},
    "MSFT": {"brands": ["Microsoft"]},
    "AMZN": {"brands": ["Amazon"]},
    "EA": {"brands": ["Electronic Arts"]},
    "ASTS": {"brands": ["AST SpaceMobile"]},
    "AAOI": {"brands": ["Applied Optoelectronics"]},
    "COST": {"brands": ["Costco"]},
    "VST": {"brands": ["Vistra"]},
    "DAL": {"brands": ["Delta Air Lines", "Delta"]},
    "PDYN": {"brands": ["Palladyne AI"]},
}

_CORP_SUFFIX_RE = re.compile(
    r"\b(Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC|L\.P\.|LP|PLC|Co\.?|Company|The)\b",
    re.I,
)
_SHARE_CLASS_RE = re.compile(
    r"\bClass\s+[A-Z0-9]+\b|\b(Common|Capital)\s+Stock\b|\bAmerican\s+Depositary\b|\bADR\b|\bADS\b",
    re.I,
)
_FUND_NAME_RE = re.compile(
    r"\b(ETF|ETN|Fund|Trust|Shares|Direxion|ProShares|SPDR|iShares|Invesco|Vanguard|Ultrapro|Bull 3X)\b",
    re.I,
)


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str = ""
    published: Optional[datetime] = None
    summary: str = ""
    provider: str = ""  # e.g. "google_news", "yahoo_rss", "yahoo_html"

    def published_label(self) -> str:
        return format_local_datetime(self.published)


def _to_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC (naive values are treated as UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert a UTC or naive datetime to the system local timezone."""
    if dt is None:
        return None
    return _to_utc(dt).astimezone()


def format_local_datetime(dt: Optional[datetime], fmt: str = "%b %d, %Y  %I:%M %p") -> str:
    """Format a datetime in the user's local timezone."""
    local = to_local_datetime(dt)
    if not local:
        return ""
    label = local.strftime(fmt)
    tz_name = (local.tzname() or "").strip()
    if tz_name and tz_name not in label:
        return f"{label} {tz_name}"
    return label


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
            # feedparser dates are UTC; timegm (not mktime) avoids local-time misinterpretation.
            return datetime.fromtimestamp(
                calendar.timegm(entry.published_parsed),
                tz=timezone.utc,
            )
        except (OverflowError, ValueError, OSError):
            pass
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return _to_utc(dt)
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


def _normalize_ticker_symbol(symbol: str) -> str:
    """Normalize ticker variants (BRK/B, BRK-B) for lookup and alias keys."""
    symbol = (symbol or "").upper().strip()
    if symbol in {"BRKB", "BRK-B", "BRK/B"}:
        return "BRK.B"
    return symbol.replace("/", ".")


def _load_history_counts() -> Dict[str, int]:
    """Load search counts from ticker_history.json, keyed by normalized symbol."""
    global _HISTORY_COUNT_CACHE
    if _HISTORY_COUNT_CACHE is not None:
        return _HISTORY_COUNT_CACHE

    counts: Dict[str, int] = {}
    try:
        if _HISTORY_FILE.is_file():
            with open(_HISTORY_FILE, encoding="utf-8") as f:
                for raw_symbol, entry in json.load(f).items():
                    canon = _normalize_ticker_symbol(raw_symbol)
                    counts[canon] = counts.get(canon, 0) + int(entry.get("count", 0))
    except Exception:
        pass

    _HISTORY_COUNT_CACHE = counts
    return counts


def _is_frequent_ticker(symbol: str) -> bool:
    return _load_history_counts().get(_normalize_ticker_symbol(symbol), 0) >= _HISTORY_MIN_COUNT


def _get_ticker_aliases(symbol: str) -> Dict[str, List[str]]:
    """Return brand/ticker overrides for symbols the user searches often."""
    canon = _normalize_ticker_symbol(symbol)
    if not _is_frequent_ticker(canon):
        return {}
    return {key: list(values) for key, values in _BRAND_OVERRIDES.get(canon, {}).items()}


def lookup_company_name(symbol: str) -> str:
    """Resolve a ticker to its company name from US_stock_symbols_verbose.json."""
    symbol = _normalize_ticker_symbol(symbol)
    if not symbol:
        return ""
    if symbol in _COMPANY_NAME_CACHE:
        return _COMPANY_NAME_CACHE[symbol]

    name = ""
    lookup_keys = [symbol]
    if symbol == "BRK.B":
        lookup_keys.append("BRK-B")
    try:
        if _VERBOSE_SYMBOLS_PATH.is_file():
            with open(_VERBOSE_SYMBOLS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            for key in lookup_keys:
                for item in data:
                    if item.get("symbol", "").upper() == key:
                        name = str(item.get("name") or "").strip()
                        break
                if name:
                    break
    except Exception:
        pass

    _COMPANY_NAME_CACHE[symbol] = name
    return name


def _normalize_company_name(raw: str) -> str:
    """Strip legal/share-class suffixes so 'Alphabet Inc. Class C' -> 'Alphabet'."""
    text = (raw or "").split(",")[0].strip()
    if not text:
        return ""
    text = _SHARE_CLASS_RE.sub(" ", text)
    text = _CORP_SUFFIX_RE.sub(" ", text)
    text = " ".join(text.split())
    return text.strip(" .")


def _is_fund_name(name: str) -> bool:
    """True when the verbose company name is really a fund/ETF description."""
    return bool(_FUND_NAME_RE.search(name or ""))


def build_news_search_terms(symbol: str, company_name: str = "") -> Dict[str, Set[str]]:
    """
    Build ticker + name keywords for news search and relevance scoring.

    Includes related tickers (GOOG/GOOGL) and brand names (Google for Alphabet).
    Brand overrides apply to tickers you search frequently (ticker_history.json).
    """
    symbol = _normalize_ticker_symbol(symbol)
    tickers: Set[str] = {symbol} if symbol else set()
    names: Set[str] = set()

    aliases = _get_ticker_aliases(symbol)
    for related in aliases.get("tickers", []):
        tickers.add(_normalize_ticker_symbol(related))

    resolved_name = company_name or lookup_company_name(symbol)
    short_name = _normalize_company_name(resolved_name)
    if short_name and short_name.upper() != symbol and not _is_fund_name(short_name):
        names.add(short_name)

    for brand in aliases.get("brands", []):
        if brand.upper() != symbol:
            names.add(brand)

    return {"tickers": tickers, "names": names}


def _format_query_term(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    if " " in term:
        return f'"{term}"'
    return term


def build_google_news_queries(symbol: str, company_name: str = "") -> List[str]:
    """Build one or more Google News RSS queries for a ticker."""
    symbol = _normalize_ticker_symbol(symbol)
    terms = build_news_search_terms(symbol, company_name=company_name)
    tickers = sorted(terms["tickers"])
    names = sorted(terms["names"])

    ticker_part = " OR ".join(tickers)
    if names:
        name_part = " OR ".join(_format_query_term(name) for name in names)
        primary = f"({ticker_part}) AND ({name_part})"
        broad = f"{ticker_part} OR {name_part} stock when:7d"
        return [primary, broad]

    return [f"{symbol} stock when:7d"]


def _article_relevance(article: NewsArticle, terms: Dict[str, Set[str]]) -> int:
    """Score how closely a headline matches the ticker/company keywords."""
    text = f"{article.title} {article.summary}".lower()
    score = 0

    for ticker in terms["tickers"]:
        ticker_l = ticker.lower()
        if ticker_l in text or f"({ticker_l})" in text:
            score += 3

    for name in terms["names"]:
        if name.lower() in text:
            score += 2

    return score


def _fetch_feed(session: requests.Session, url: str) -> feedparser.FeedParserDict:
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def fetch_google_news_rss(symbol: str, company_name: str = "", limit: int = DEFAULT_LIMIT) -> List[NewsArticle]:
    """Google News RSS search — primary source for ticker-relevant headlines."""
    symbol = symbol.upper().strip()
    queries = build_google_news_queries(symbol, company_name=company_name)
    session = _session()
    articles: List[NewsArticle] = []

    for query in queries:
        url = (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            feed = _fetch_feed(session, url)
        except Exception:
            continue
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
        if len(_dedupe(articles)) >= limit:
            break

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

    resolved_name = company_name or lookup_company_name(symbol)
    search_terms = build_news_search_terms(symbol, company_name=resolved_name)
    collected: List[NewsArticle] = []

    try:
        collected.extend(
            fetch_google_news_rss(symbol, company_name=resolved_name, limit=limit)
        )
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
    fallback_ts = result.fetched_at

    scored: List[Tuple[NewsArticle, int]] = [
        (article, _article_relevance(article, search_terms)) for article in merged
    ]
    relevant = [article for article, score in scored if score > 0]
    if len(relevant) >= max(3, limit // 2):
        merged = relevant
    else:
        merged = [article for article, _ in scored]

    provider_rank = {"google_news": 0, "yahoo_rss": 1, "yahoo_html": 2}
    merged.sort(
        key=lambda a: (
            -_article_relevance(a, search_terms),
            provider_rank.get(a.provider, 9),
            -(a.published or fallback_ts).timestamp(),
        )
    )
    result.articles = merged[:limit]
    if not result.articles and not result.errors:
        result.errors.append("No articles found.")
    return result
