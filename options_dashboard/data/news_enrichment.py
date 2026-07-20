"""
Background news enrichment: headlines → article text → LLM summary + sentiment.

Runs in parallel with options fetches so Headline News can open with results ready.
Persists per-ticker results under state/news_cache/ and refreshes in the background.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, Set
import threading

from data.article_summary import fetch_and_summarize
from data.news_cache import (
    MAX_CACHED_ARTICLES,
    article_identity,
    filter_fresh_articles,
    load_news_cache,
    merge_news_results,
    save_news_cache,
)
from data.news_scraper import NewsArticle, fetch_stock_news
from data.ollama_summarizer import (
    SentimentResult,
    check_ollama,
    summarize_with_ollama,
)

DEFAULT_ARTICLE_LIMIT = 8
_DOWNLOAD_WORKERS = 3
# Ollama typically handles one generation well; serialize across tickers.
_OLLAMA_LOCK = threading.Lock()


@dataclass
class EnrichedArticle:
    article: NewsArticle
    llm_summary: str = ""
    sentiment: Optional[SentimentResult] = None
    title: str = ""
    final_url: str = ""
    text: str = ""
    error: str = ""
    ready: bool = False

    @property
    def display_title(self) -> str:
        return (self.title or self.article.title or "Untitled").strip()

    @property
    def open_url(self) -> str:
        return self.final_url or self.article.link


@dataclass
class NewsEnrichmentResult:
    symbol: str
    articles: List[EnrichedArticle] = field(default_factory=list)
    status: str = "idle"  # idle | loading | refreshing | ready | error
    errors: List[str] = field(default_factory=list)
    fetched_at: Optional[datetime] = None
    generation: int = 0
    # Articles newly added by the latest refresh (for live UI appends).
    new_articles: List[EnrichedArticle] = field(default_factory=list)
    from_cache: bool = False

    @property
    def ready(self) -> bool:
        return self.status in ("ready", "refreshing") and bool(self.articles)

    @property
    def is_refreshing(self) -> bool:
        return self.status == "refreshing"


def _enrich_articles(
    articles: List[NewsArticle],
    *,
    model: str,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> tuple[List[EnrichedArticle], List[str]]:
    """Download bodies + LLM-summarize a list of headline articles."""
    errors: List[str] = []
    if not articles:
        return [], errors

    ollama = check_ollama()
    if not ollama.reachable:
        errors.append(
            "Ollama is offline. Headlines loaded without LLM summaries/sentiment."
        )
        return [
            EnrichedArticle(
                article=a,
                title=a.title,
                final_url=a.link,
                error="Ollama offline — start Ollama for LLM summaries.",
                ready=True,
            )
            for a in articles
        ], errors

    downloaded: List[EnrichedArticle] = []

    def _download_only(article: NewsArticle) -> EnrichedArticle:
        out = EnrichedArticle(article=article, title=article.title, final_url=article.link)
        try:
            content = fetch_and_summarize(
                article.link,
                title_hint=article.title,
                rss_fallback=article.summary or "",
                max_sentences=5,
            )
            out.title = content.title or article.title
            out.final_url = content.final_url or article.link
            out.text = content.text or content.summary or article.summary or ""
            if content.errors:
                out.error = content.errors[-1]
        except Exception as exc:
            out.error = str(exc)
            out.text = article.summary or ""
        return out

    with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(_download_only, a): a for a in articles}
        for fut in as_completed(futures):
            if should_cancel and should_cancel():
                errors.append("Cancelled.")
                return downloaded, errors
            downloaded.append(fut.result())

    by_link = {e.article.link: e for e in downloaded}
    ordered = [by_link.get(a.link) or EnrichedArticle(article=a) for a in articles]

    for item in ordered:
        if should_cancel and should_cancel():
            errors.append("Cancelled.")
            break

        text_for_llm = (item.text or "").strip()
        if not text_for_llm:
            item.error = item.error or "No article text available for LLM."
            item.ready = True
            continue

        try:
            with _OLLAMA_LOCK:
                llm = summarize_with_ollama(
                    text_for_llm,
                    title=item.title or item.article.title,
                    model=model,
                    include_sentiment=True,
                )
            if llm.ok:
                item.llm_summary = llm.summary
                item.sentiment = llm.sentiment
                if not (item.error and "RSS" in item.error):
                    item.error = ""
            else:
                item.error = llm.error or "LLM summary failed."
        except Exception as exc:
            item.error = str(exc)
        item.ready = True

    return ordered, errors


def enrich_symbol_news(
    symbol: str,
    *,
    company_name: str = "",
    limit: int = DEFAULT_ARTICLE_LIMIT,
    model: str = "",
    should_cancel: Optional[Callable[[], bool]] = None,
    known_keys: Optional[Set[str]] = None,
) -> NewsEnrichmentResult:
    """
    Blocking: fetch headlines, download bodies, LLM-summarize each.
    If known_keys is set, only enrich articles not already cached.
    """
    from data.ollama_summarizer import DEFAULT_MODEL

    symbol = (symbol or "").strip().upper()
    model = model or DEFAULT_MODEL
    result = NewsEnrichmentResult(symbol=symbol, status="loading")
    known_keys = known_keys or set()

    if not symbol:
        result.status = "error"
        result.errors.append("No symbol.")
        return result

    if should_cancel and should_cancel():
        result.status = "error"
        result.errors.append("Cancelled.")
        return result

    # Pull a wider net when refreshing so we can discover new headlines.
    fetch_limit = max(limit, min(MAX_CACHED_ARTICLES, limit * 3))
    news = fetch_stock_news(symbol, company_name=company_name, limit=fetch_limit)
    result.errors.extend(news.errors)
    result.fetched_at = news.fetched_at or datetime.now(timezone.utc)
    # Ignore headlines older than MAX_ARTICLE_AGE_DAYS (calendar days vs today)
    news.articles = filter_fresh_articles(
        news.articles,
        undated_fallback=result.fetched_at,
    )

    if should_cancel and should_cancel():
        result.status = "error"
        result.errors.append("Cancelled.")
        return result

    if not news.articles:
        result.status = "error"
        result.errors.append(
            result.errors[-1]
            if result.errors
            else "No recent headlines found (within last 5 days)."
        )
        return result

    if known_keys:
        to_enrich = [
            a for a in news.articles if article_identity(a) not in known_keys
        ][:limit]
    else:
        to_enrich = news.articles[:limit]

    if not to_enrich:
        result.articles = []
        result.status = "ready"
        return result

    enriched, enrich_errors = _enrich_articles(
        to_enrich,
        model=model,
        should_cancel=should_cancel,
    )
    result.errors.extend(enrich_errors)
    if should_cancel and should_cancel():
        result.status = "error"
        result.errors.append("Cancelled.")
        return result

    result.articles = enriched
    result.status = "ready" if enriched else "error"
    if not enriched and not result.errors:
        result.errors.append("No articles enriched.")
    return result


class NewsEnrichmentController:
    """Per-dashboard cache + generation tokens so stale workers don't clobber UI."""

    def __init__(self, root):
        self.root = root
        self._lock = threading.Lock()
        self.by_symbol: dict[str, NewsEnrichmentResult] = {}
        self._generation: dict[str, int] = {}
        self._listeners: List[Callable[[str, NewsEnrichmentResult], None]] = []

    def add_listener(self, cb: Callable[[str, NewsEnrichmentResult], None]) -> None:
        if cb not in self._listeners:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[str, NewsEnrichmentResult], None]) -> None:
        try:
            self._listeners.remove(cb)
        except ValueError:
            pass

    def get(self, symbol: str) -> Optional[NewsEnrichmentResult]:
        symbol = (symbol or "").strip().upper()
        with self._lock:
            return self.by_symbol.get(symbol)

    def seed(self, result: NewsEnrichmentResult) -> None:
        """Place a cached result into memory if nothing richer is present."""
        symbol = (result.symbol or "").strip().upper()
        if not symbol or not result.articles:
            return
        with self._lock:
            current = self.by_symbol.get(symbol)
            if current and current.articles and current.status in ("loading", "refreshing", "ready"):
                return
            self.by_symbol[symbol] = result

    def is_ready(self, symbol: str) -> bool:
        entry = self.get(symbol)
        return bool(entry and entry.ready)

    def is_loading(self, symbol: str) -> bool:
        entry = self.get(symbol)
        return bool(entry and entry.status in ("loading", "refreshing"))

    def _notify(self, symbol: str, entry: NewsEnrichmentResult) -> None:
        for cb in list(self._listeners):
            try:
                cb(symbol, entry)
            except Exception:
                pass

    def start(
        self,
        symbol: str,
        *,
        company_name: str = "",
        limit: int = DEFAULT_ARTICLE_LIMIT,
    ) -> None:
        symbol = (symbol or "").strip().upper()
        if not symbol:
            return

        cached = load_news_cache(symbol)

        with self._lock:
            gen = self._generation.get(symbol, 0) + 1
            self._generation[symbol] = gen

            if cached and cached.articles:
                pending = NewsEnrichmentResult(
                    symbol=symbol,
                    articles=list(cached.articles),
                    status="refreshing",
                    errors=list(cached.errors or []),
                    fetched_at=cached.fetched_at,
                    generation=gen,
                    from_cache=True,
                )
            else:
                pending = NewsEnrichmentResult(
                    symbol=symbol,
                    status="loading",
                    generation=gen,
                )
            self.by_symbol[symbol] = pending

        self.root.after(0, lambda: self._notify(symbol, pending))

        def worker():
            def cancelled() -> bool:
                with self._lock:
                    return self._generation.get(symbol, 0) != gen

            with self._lock:
                baseline = self.by_symbol.get(symbol)
                known = {
                    article_identity(a)
                    for a in (baseline.articles if baseline else [])
                }

            fresh = enrich_symbol_news(
                symbol,
                company_name=company_name,
                limit=limit,
                should_cancel=cancelled,
                known_keys=known if known else None,
            )
            fresh.generation = gen

            if cancelled():
                return

            with self._lock:
                existing = self.by_symbol.get(symbol)
                # Prefer in-memory baseline (may include cache) for merge
                merge_base = existing if (existing and existing.articles) else cached

            if fresh.status == "error" and not fresh.articles:
                # Keep showing cached articles if refresh failed
                if merge_base and merge_base.articles:
                    kept = NewsEnrichmentResult(
                        symbol=symbol,
                        articles=list(merge_base.articles),
                        status="ready",
                        errors=list(merge_base.errors or []) + list(fresh.errors or []),
                        fetched_at=merge_base.fetched_at,
                        generation=gen,
                        from_cache=True,
                    )
                    save_news_cache(kept)
                    with self._lock:
                        if self._generation.get(symbol, 0) != gen:
                            return
                        self.by_symbol[symbol] = kept
                    self.root.after(0, lambda: self._notify(symbol, kept))
                    return

                with self._lock:
                    if self._generation.get(symbol, 0) != gen:
                        return
                    self.by_symbol[symbol] = fresh
                self.root.after(0, lambda: self._notify(symbol, fresh))
                return

            merged, new_items = merge_news_results(
                merge_base,
                fresh,
                limit=MAX_CACHED_ARTICLES,
            )
            merged.generation = gen
            merged.new_articles = new_items
            merged.from_cache = False
            merged.status = "ready"
            save_news_cache(merged)

            with self._lock:
                if self._generation.get(symbol, 0) != gen:
                    return
                self.by_symbol[symbol] = merged

            self.root.after(0, lambda: self._notify(symbol, merged))

        threading.Thread(target=worker, daemon=True).start()
