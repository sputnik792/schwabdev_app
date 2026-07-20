"""
Per-ticker persisted news state.

Each symbol gets a JSON file under options_dashboard/state/news_cache/
so Headline News can reopen previously enriched articles without re-scraping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import json
import re

from data.news_scraper import (
    MAX_ARTICLE_AGE_DAYS,
    NewsArticle,
    _normalize_ticker_symbol,
    is_within_article_age,
)
from data.ollama_summarizer import SentimentResult

if TYPE_CHECKING:
    from data.news_enrichment import EnrichedArticle, NewsEnrichmentResult

NEWS_CACHE_DIR = Path(__file__).resolve().parents[1] / "state" / "news_cache"
MAX_CACHED_ARTICLES = 40
_MAX_TEXT_CHARS = 12_000

_SAFE_SYMBOL_RE = re.compile(r"[^A-Z0-9._-]+")


def news_cache_dir() -> Path:
    NEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return NEWS_CACHE_DIR


def _cache_path(symbol: str) -> Path:
    symbol = _normalize_ticker_symbol(symbol)
    safe = _SAFE_SYMBOL_RE.sub("_", symbol) or "UNKNOWN"
    return news_cache_dir() / f"{safe}.json"


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _dt_from_iso(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        text = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def filter_fresh_articles(
    articles: List[Any],
    *,
    now: Optional[datetime] = None,
    max_age_days: int = MAX_ARTICLE_AGE_DAYS,
    undated_fallback: Optional[datetime] = None,
) -> List[Any]:
    """Keep only articles within max_age_days of today (NewsArticle or EnrichedArticle)."""
    from data.news_enrichment import EnrichedArticle

    now = now or datetime.now(timezone.utc)
    kept: List[Any] = []
    for item in articles:
        if isinstance(item, EnrichedArticle):
            published = item.article.published
        else:
            published = getattr(item, "published", None)
        if is_within_article_age(
            published,
            now=now,
            max_age_days=max_age_days,
            undated_fallback=undated_fallback,
        ):
            kept.append(item)
    return kept


def article_identity(article) -> str:
    """Stable key for deduping cached vs freshly scraped articles."""
    from data.news_enrichment import EnrichedArticle

    if isinstance(article, EnrichedArticle):
        link = (article.final_url or article.article.link or "").strip().lower()
        title = (article.display_title or "").strip().lower()
    else:
        link = (getattr(article, "link", "") or "").strip().lower()
        title = (getattr(article, "title", "") or "").strip().lower()
    return link or title


def _serialize_sentiment(sentiment: Optional[SentimentResult]) -> Optional[Dict[str, Any]]:
    if not sentiment:
        return None
    return {
        "label": sentiment.label,
        "reason": sentiment.reason,
        "model": sentiment.model,
        "elapsed_sec": sentiment.elapsed_sec,
        "error": sentiment.error,
    }


def _deserialize_sentiment(data: Any) -> Optional[SentimentResult]:
    if not isinstance(data, dict):
        return None
    return SentimentResult(
        label=str(data.get("label") or "neutral"),
        reason=str(data.get("reason") or ""),
        model=str(data.get("model") or ""),
        elapsed_sec=float(data.get("elapsed_sec") or 0.0),
        error=str(data.get("error") or ""),
    )


def _serialize_article(item) -> Dict[str, Any]:
    art = item.article
    text = item.text or ""
    if len(text) > _MAX_TEXT_CHARS:
        text = text[: _MAX_TEXT_CHARS - 1].rstrip() + "…"
    return {
        "title": art.title,
        "link": art.link,
        "source": art.source,
        "published": _dt_to_iso(art.published),
        "summary": art.summary,
        "provider": art.provider,
        "display_title": item.title,
        "final_url": item.final_url,
        "llm_summary": item.llm_summary,
        "text": text,
        "error": item.error,
        "ready": bool(item.ready),
        "sentiment": _serialize_sentiment(item.sentiment),
    }


def _deserialize_article(data: Dict[str, Any]):
    from data.news_enrichment import EnrichedArticle

    link = str(data.get("link") or "").strip()
    title = str(data.get("title") or data.get("display_title") or "").strip()
    if not link and not title:
        return None
    article = NewsArticle(
        title=title or "Untitled",
        link=link or str(data.get("final_url") or ""),
        source=str(data.get("source") or ""),
        published=_dt_from_iso(data.get("published")),
        summary=str(data.get("summary") or ""),
        provider=str(data.get("provider") or "cache"),
    )
    return EnrichedArticle(
        article=article,
        llm_summary=str(data.get("llm_summary") or ""),
        sentiment=_deserialize_sentiment(data.get("sentiment")),
        title=str(data.get("display_title") or title),
        final_url=str(data.get("final_url") or link),
        text=str(data.get("text") or ""),
        error=str(data.get("error") or ""),
        ready=bool(data.get("ready", True)),
    )


def serialize_news_result(result) -> Dict[str, Any]:
    return {
        "symbol": _normalize_ticker_symbol(result.symbol),
        "status": result.status,
        "errors": list(result.errors or []),
        "fetched_at": _dt_to_iso(result.fetched_at),
        "updated_at": _dt_to_iso(datetime.now(timezone.utc)),
        "articles": [_serialize_article(a) for a in result.articles],
    }


def deserialize_news_result(data: Dict[str, Any]):
    from data.news_enrichment import NewsEnrichmentResult

    articles = []
    for raw in data.get("articles") or []:
        if not isinstance(raw, dict):
            continue
        item = _deserialize_article(raw)
        if item:
            articles.append(item)
    status = str(data.get("status") or "ready")
    if articles and status == "loading":
        status = "ready"
    return NewsEnrichmentResult(
        symbol=_normalize_ticker_symbol(str(data.get("symbol") or "")),
        articles=articles,
        status=status if articles else "idle",
        errors=list(data.get("errors") or []),
        fetched_at=_dt_from_iso(data.get("fetched_at")),
    )


def load_news_cache(symbol: str):
    path = _cache_path(symbol)
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        result = deserialize_news_result(data)
        if not result.symbol:
            result.symbol = _normalize_ticker_symbol(symbol)
        # Drop anything older than MAX_ARTICLE_AGE_DAYS vs today
        fresh = filter_fresh_articles(
            result.articles,
            undated_fallback=result.fetched_at,
        )
        if len(fresh) != len(result.articles):
            result.articles = fresh
            if fresh:
                # Rewrite cache without the expired rows
                save_news_cache(result)
        if not result.articles:
            return None
        result.status = "ready"
        return result
    except Exception as exc:
        print(f"[NEWS CACHE] Failed to load {path.name}: {exc}")
        return None


def save_news_cache(result) -> None:
    symbol = _normalize_ticker_symbol(result.symbol)
    if not symbol:
        return
    from data.news_enrichment import NewsEnrichmentResult

    fresh = filter_fresh_articles(
        list(result.articles or []),
        undated_fallback=result.fetched_at,
    )[:MAX_CACHED_ARTICLES]
    if not fresh:
        # Nothing recent left — remove stale cache file if present
        path = _cache_path(symbol)
        try:
            if path.is_file():
                path.unlink()
        except Exception:
            pass
        return

    trimmed = NewsEnrichmentResult(
        symbol=symbol,
        articles=fresh,
        status="ready",
        errors=list(result.errors or []),
        fetched_at=result.fetched_at or datetime.now(timezone.utc),
        generation=result.generation,
    )
    path = _cache_path(symbol)
    try:
        news_cache_dir()
        payload = serialize_news_result(trimmed)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
    except Exception as exc:
        print(f"[NEWS CACHE] Failed to save {symbol}: {exc}")


def merge_news_results(
    existing,
    incoming,
    *,
    limit: int = MAX_CACHED_ARTICLES,
) -> Tuple[Any, List[Any]]:
    """
    Merge scraped/enriched articles into an existing cache.
    Returns (merged_result, newly_added_articles).
    """
    from data.news_enrichment import NewsEnrichmentResult

    symbol = _normalize_ticker_symbol(
        incoming.symbol or (existing.symbol if existing else "")
    )
    by_key: Dict[str, Any] = {}
    order: List[str] = []
    now = datetime.now(timezone.utc)
    undated_fallback = incoming.fetched_at or (
        existing.fetched_at if existing else now
    )

    def _add(item, *, prefer_new: bool) -> None:
        key = article_identity(item)
        if not key:
            return
        published = item.article.published
        if not is_within_article_age(
            published,
            now=now,
            undated_fallback=undated_fallback,
        ):
            return
        if key not in by_key:
            by_key[key] = item
            order.append(key)
            return
        if prefer_new:
            old = by_key[key]
            if item.llm_summary or not old.llm_summary:
                by_key[key] = item
            elif item.sentiment and not old.sentiment:
                by_key[key] = item

    prior_keys = set()
    if existing:
        for item in existing.articles:
            _add(item, prefer_new=False)
            prior_keys.add(article_identity(item))

    new_items = []
    new_keys_seen = set()
    for item in incoming.articles:
        key = article_identity(item)
        if key and key not in prior_keys and key not in new_keys_seen:
            if is_within_article_age(
                item.article.published,
                now=now,
                undated_fallback=undated_fallback,
            ):
                new_items.append(item)
                new_keys_seen.add(key)
        _add(item, prefer_new=True)

    merged_articles = [by_key[k] for k in order]
    fallback = incoming.fetched_at or datetime.now(timezone.utc)

    def _ts(item) -> float:
        pub = item.article.published
        return (pub or fallback).timestamp()

    merged_articles.sort(key=_ts, reverse=True)
    merged_articles = merged_articles[:limit]

    kept_keys = {article_identity(a) for a in merged_articles}
    new_items = [a for a in new_items if article_identity(a) in kept_keys]
    new_items.sort(key=_ts, reverse=True)

    errors: List[str] = []
    if existing:
        errors.extend(existing.errors or [])
    errors.extend(incoming.errors or [])
    seen_err = set()
    uniq_errors = []
    for err in errors:
        if err and err not in seen_err:
            seen_err.add(err)
            uniq_errors.append(err)

    merged = NewsEnrichmentResult(
        symbol=symbol,
        articles=merged_articles,
        status="ready",
        errors=uniq_errors[-5:],
        fetched_at=incoming.fetched_at or (existing.fetched_at if existing else fallback),
        generation=incoming.generation,
    )
    return merged, new_items
