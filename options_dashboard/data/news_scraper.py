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
# Drop headlines whose publish date is older than this many calendar days vs today.
MAX_ARTICLE_AGE_DAYS = 5

_VERBOSE_SYMBOLS_PATH = (
    Path(__file__).resolve().parents[1] / "US_stock_symbols_verbose.json"
)
_COMPANY_NAME_CACHE: Dict[str, str] = {}

# Brand / related-ticker / finance-keyword overrides.
# Keys use normalized symbols (BRK/B -> BRK.B).
# - brands: how news usually names the company
# - tickers: related symbols (share classes, dual listings)
# - keywords: financially relevant products, segments, catalysts often in headlines
_BRAND_OVERRIDES: Dict[str, Dict[str, List[str]]] = {
    # ETFs & leveraged products
    "SPY": {
        "brands": ["S&P 500", "S&P"],
        "keywords": ["index futures", "equity futures", "Wall Street", "stock market"],
    },
    "QQQ": {
        "brands": ["Nasdaq 100", "Nasdaq"],
        "keywords": ["tech stocks", "Magnificent Seven", "growth stocks"],
    },
    "SOXL": {
        "brands": ["semiconductor", "chip stocks"],
        "keywords": ["chipmaker", "foundry", "memory chips", "AI chips", "semis"],
    },
    "TQQQ": {
        "tickers": ["QQQ"],
        "brands": ["Nasdaq", "Nasdaq 100"],
        "keywords": ["tech stocks", "leveraged ETF", "Nasdaq rally"],
    },
    "XLV": {
        "brands": ["healthcare sector", "health care"],
        "keywords": ["pharma stocks", "biotech", "drug stocks"],
    },
    # Dual tickers / brand != legal name
    "GOOG": {
        "tickers": ["GOOGL"],
        "brands": ["Google", "Alphabet"],
        "keywords": [
            "Google Cloud",
            "YouTube",
            "Gemini",
            "ad revenue",
            "search advertising",
            "Waymo",
        ],
    },
    "GOOGL": {
        "tickers": ["GOOG"],
        "brands": ["Google", "Alphabet"],
        "keywords": [
            "Google Cloud",
            "YouTube",
            "Gemini",
            "ad revenue",
            "search advertising",
            "Waymo",
        ],
    },
    "META": {
        "brands": ["Meta", "Facebook"],
        "keywords": ["Instagram", "WhatsApp", "Reels", "ad revenue", "AI spending", "Reality Labs"],
    },
    "FB": {
        "tickers": ["META"],
        "brands": ["Meta", "Facebook"],
        "keywords": ["Instagram", "WhatsApp", "ad revenue"],
    },
    "BRK.A": {
        "tickers": ["BRK.B"],
        "brands": ["Berkshire Hathaway", "Berkshire"],
        "keywords": ["Warren Buffett", "Buffett", "insurance float", "operating earnings"],
    },
    "BRK.B": {
        "tickers": ["BRK.A"],
        "brands": ["Berkshire Hathaway", "Berkshire"],
        "keywords": ["Warren Buffett", "Buffett", "insurance float", "operating earnings"],
    },
    # Frequently searched stocks (from ticker_history.json)
    "DELL": {
        "brands": ["Dell"],
        "keywords": ["AI servers", "server demand", "PC sales", "data center", "PowerEdge"],
    },
    "AXTI": {
        "brands": ["AXT"],
        "keywords": ["compound semiconductor", "wafer", "gallium arsenide", "InP", "substrate"],
    },
    "NVDA": {
        "brands": ["Nvidia"],
        "keywords": ["GPU", "AI chips", "data center", "CUDA", "Blackwell", "H100", "chip demand"],
    },
    "TSLA": {
        "brands": ["Tesla"],
        "keywords": ["EV deliveries", "autopilot", "FSD", "Cybertruck", "energy storage", "Gigafactory"],
    },
    "MRVL": {
        "brands": ["Marvell"],
        "keywords": ["custom silicon", "AI accelerators", "networking chips", "optical DSP", "data center"],
    },
    "MU": {
        "brands": ["Micron"],
        "keywords": ["DRAM", "HBM", "NAND", "memory chips", "AI memory", "chip cycle"],
    },
    "COHR": {
        "brands": ["Coherent"],
        "keywords": ["optical communications", "lasers", "transceivers", "datacom", "AI networking"],
    },
    "PANW": {
        "brands": ["Palo Alto Networks", "Palo Alto"],
        "keywords": ["cybersecurity", "firewall", "Prisma", "security software", "cloud security"],
    },
    "PLTR": {
        "brands": ["Palantir"],
        "keywords": ["AIP", "government contracts", "commercial bookings", "data analytics", "AI platform"],
    },
    "AVGO": {
        "brands": ["Broadcom"],
        "keywords": ["custom AI chips", "VMware", "networking ASICs", "semiconductor", "data center"],
    },
    "LITE": {
        "brands": ["Lumentum"],
        "keywords": ["optical components", "transceivers", "datacom", "lasers", "AI networking"],
    },
    "AMD": {
        "brands": ["Advanced Micro Devices"],
        "keywords": ["EPYC", "Ryzen", "MI300", "AI GPUs", "data center CPUs", "chip rivalry"],
    },
    "ADBE": {
        "brands": ["Adobe"],
        "keywords": ["Creative Cloud", "Firefly", "subscription revenue", "digital media", "PDF"],
    },
    "TGT": {
        "brands": ["Target"],
        "keywords": ["same-store sales", "retail sales", "consumer spending", "inventory", "discount retail"],
    },
    "BRKR": {
        "brands": ["Bruker"],
        "keywords": ["scientific instruments", "life science", "analytical instruments", "biopharma tools"],
    },
    "PFE": {
        "brands": ["Pfizer"],
        "keywords": ["drug pipeline", "vaccine", "pharma earnings", "FDA approval", "prescription drugs"],
    },
    "AAPL": {
        "brands": ["Apple"],
        "keywords": ["iPhone", "App Store", "Services revenue", "Mac", "AI features", "China sales"],
    },
    "ORCL": {
        "brands": ["Oracle"],
        "keywords": ["cloud infrastructure", "database", "AI cloud", "OCI", "enterprise software"],
    },
    "MSFT": {
        "brands": ["Microsoft"],
        "keywords": ["Azure", "OpenAI", "Copilot", "cloud revenue", "Windows", "Office 365"],
    },
    "AMZN": {
        "brands": ["Amazon"],
        "keywords": ["AWS", "e-commerce", "advertising", "Prime", "cloud computing", "retail sales"],
    },
    "EA": {
        "brands": ["Electronic Arts"],
        "keywords": ["video games", "live services", "sports titles", "game bookings", "mobile gaming"],
    },
    "ASTS": {
        "brands": ["AST SpaceMobile"],
        "keywords": ["satellite broadband", "space-based cellular", "mobile connectivity", "spectrum"],
    },
    "AAOI": {
        "brands": ["Applied Optoelectronics"],
        "keywords": ["optical transceivers", "datacom", "fiber optics", "AI networking"],
    },
    "COST": {
        "brands": ["Costco"],
        "keywords": ["membership fees", "warehouse clubs", "comparable sales", "retail traffic"],
    },
    "VST": {
        "brands": ["Vistra"],
        "keywords": ["power generation", "electricity demand", "AI data centers", "energy prices", "utilities"],
    },
    "DAL": {
        "brands": ["Delta Air Lines", "Delta"],
        "keywords": ["airline capacity", "passenger demand", "unit revenue", "jet fuel", "travel demand"],
    },
    "PDYN": {
        "brands": ["Palladyne AI"],
        "keywords": ["robotics software", "autonomous systems", "defense robotics"],
    },
    "RBLX": {
        "brands": ["Roblox"],
        "keywords": ["user engagement", "bookings", "metaverse", "creator economy", "gaming platform"],
    },
}

# Generic finance context — only used when paired with ticker/brand (never alone).
_FINANCE_CONTEXT_TERMS = [
    "earnings",
    "stock",
    "shares",
    "analyst",
    "guidance",
    "revenue",
]

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


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_within_article_age(
    published: Optional[datetime],
    *,
    now: Optional[datetime] = None,
    max_age_days: int = MAX_ARTICLE_AGE_DAYS,
    undated_fallback: Optional[datetime] = None,
) -> bool:
    """
    True if publish date is within max_age_days of today's date.

    Undated articles use undated_fallback when provided; otherwise they are kept.
    """
    now = _as_utc(now or datetime.now(timezone.utc))
    today = now.date()
    stamp = published or undated_fallback
    if stamp is None:
        return True
    stamp = _as_utc(stamp)
    return (today - stamp.date()).days <= max_age_days


def filter_fresh_news_articles(
    articles: Iterable[NewsArticle],
    *,
    now: Optional[datetime] = None,
    max_age_days: int = MAX_ARTICLE_AGE_DAYS,
    undated_fallback: Optional[datetime] = None,
) -> List[NewsArticle]:
    """Keep only NewsArticle rows within the age window."""
    now = now or datetime.now(timezone.utc)
    return [
        a
        for a in articles
        if is_within_article_age(
            a.published,
            now=now,
            max_age_days=max_age_days,
            undated_fallback=undated_fallback,
        )
    ]


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


def _get_ticker_aliases(symbol: str) -> Dict[str, List[str]]:
    """Return brand/ticker/keyword overrides when the symbol is in the lookup table."""
    canon = _normalize_ticker_symbol(symbol)
    entry = _BRAND_OVERRIDES.get(canon)
    if not entry:
        return {}
    return {key: list(values) for key, values in entry.items()}


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
    Build ticker + name + finance keywords for news search and relevance scoring.

    Includes related tickers (GOOG/GOOGL), brand names, and financially relevant
    product/segment keywords from the lookup table.
    """
    symbol = _normalize_ticker_symbol(symbol)
    tickers: Set[str] = {symbol} if symbol else set()
    names: Set[str] = set()
    keywords: Set[str] = set()

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

    for kw in aliases.get("keywords", []):
        keywords.add(kw)

    return {"tickers": tickers, "names": names, "keywords": keywords}


def _format_query_term(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    if " " in term or "&" in term:
        return f'"{term}"'
    return term


def _or_group(terms: Iterable[str]) -> str:
    parts = [_format_query_term(t) for t in terms if t and str(t).strip()]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + " OR ".join(parts) + ")"


def build_google_news_queries(symbol: str, company_name: str = "") -> List[str]:
    """Build Google News RSS queries using ticker, brand, and finance keywords."""
    symbol = _normalize_ticker_symbol(symbol)
    terms = build_news_search_terms(symbol, company_name=company_name)
    tickers = sorted(terms["tickers"])
    names = sorted(terms["names"])
    keywords = sorted(terms["keywords"])

    entity_terms = list(tickers) + list(names)
    entity_group = _or_group(entity_terms)
    queries: List[str] = []

    # 1) Tight: ticker must co-occur with brand/company name
    if names:
        queries.append(f"{_or_group(tickers)} AND {_or_group(names)}")

    # 2) Finance-focused: entity + company-specific finance keywords
    if entity_group and keywords:
        # Cap keywords in the query so Google News stays focused
        kw_group = _or_group(keywords[:6])
        queries.append(f"{entity_group} AND {kw_group} when:7d")

    # 3) Generic finance context paired with the entity (never keywords alone)
    if entity_group:
        finance_group = _or_group(_FINANCE_CONTEXT_TERMS)
        queries.append(f"{entity_group} AND {finance_group} when:7d")

    # 4) Broad fallback
    if names:
        queries.append(f"{_or_group(tickers + names)} stock when:7d")
    else:
        queries.append(f"{symbol} stock when:7d")

    # Preserve order, drop empties/dupes
    seen = set()
    out: List[str] = []
    for q in queries:
        q = " ".join(q.split())
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _article_relevance(article: NewsArticle, terms: Dict[str, Set[str]]) -> int:
    """Score how closely a headline matches ticker/company/finance keywords."""
    text = f"{article.title} {article.summary}".lower()
    score = 0

    for ticker in terms.get("tickers", ()):
        ticker_l = ticker.lower()
        if ticker_l in text or f"({ticker_l})" in text:
            score += 3

    for name in terms.get("names", ()):
        if name.lower() in text:
            score += 2

    for kw in terms.get("keywords", ()):
        if kw.lower() in text:
            score += 2

    # Light boost when a finance-context word appears with an entity match
    if score > 0:
        for ctx in _FINANCE_CONTEXT_TERMS:
            if ctx.lower() in text:
                score += 1
                break

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
    # Newest first; relevance / provider only break ties on the same timestamp.
    merged.sort(
        key=lambda a: (
            -(a.published or fallback_ts).timestamp(),
            -_article_relevance(a, search_terms),
            provider_rank.get(a.provider, 9),
        )
    )
    # Drop headlines older than MAX_ARTICLE_AGE_DAYS vs today
    merged = filter_fresh_news_articles(merged, undated_fallback=fallback_ts)
    result.articles = merged[:limit]
    if not result.articles and not result.errors:
        result.errors.append("No articles found.")
    return result
