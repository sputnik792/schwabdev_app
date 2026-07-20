"""
Background news enrichment: headlines → article text → LLM summary + sentiment.

Runs in parallel with options fetches so Headline News can open with results ready.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional
import threading

from data.article_summary import fetch_and_summarize
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
    status: str = "idle"  # idle | loading | ready | error
    errors: List[str] = field(default_factory=list)
    fetched_at: Optional[datetime] = None
    generation: int = 0

    @property
    def ready(self) -> bool:
        return self.status == "ready" and bool(self.articles)


def enrich_symbol_news(
    symbol: str,
    *,
    company_name: str = "",
    limit: int = DEFAULT_ARTICLE_LIMIT,
    model: str = "",
    should_cancel: Optional[Callable[[], bool]] = None,
) -> NewsEnrichmentResult:
    """
    Blocking: fetch headlines, download bodies, LLM-summarize each.
    Call from a worker thread.
    """
    from data.ollama_summarizer import DEFAULT_MODEL

    symbol = (symbol or "").strip().upper()
    model = model or DEFAULT_MODEL
    result = NewsEnrichmentResult(symbol=symbol, status="loading")

    if not symbol:
        result.status = "error"
        result.errors.append("No symbol.")
        return result

    if should_cancel and should_cancel():
        result.status = "error"
        result.errors.append("Cancelled.")
        return result

    news = fetch_stock_news(symbol, company_name=company_name, limit=limit)
    result.errors.extend(news.errors)
    result.fetched_at = news.fetched_at or datetime.now(timezone.utc)

    if should_cancel and should_cancel():
        result.status = "error"
        result.errors.append("Cancelled.")
        return result

    if not news.articles:
        result.status = "error"
        result.errors.append(result.errors[-1] if result.errors else "No headlines found.")
        return result

    ollama = check_ollama()
    if not ollama.reachable:
        result.articles = [
            EnrichedArticle(
                article=a,
                title=a.title,
                final_url=a.link,
                error="Ollama offline — start Ollama for LLM summaries.",
                ready=True,
            )
            for a in news.articles
        ]
        result.status = "ready"
        result.errors.append(
            "Ollama is offline. Headlines loaded without LLM summaries/sentiment."
        )
        return result

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
        futures = {pool.submit(_download_only, a): a for a in news.articles}
        for fut in as_completed(futures):
            if should_cancel and should_cancel():
                result.status = "error"
                result.errors.append("Cancelled.")
                return result
            downloaded.append(fut.result())

    by_link = {e.article.link: e for e in downloaded}
    ordered = [by_link.get(a.link) or EnrichedArticle(article=a) for a in news.articles]

    for item in ordered:
        if should_cancel and should_cancel():
            result.status = "error"
            result.errors.append("Cancelled.")
            return result

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

    result.articles = ordered
    result.status = "ready"
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
        self._listeners.append(cb)

    def get(self, symbol: str) -> Optional[NewsEnrichmentResult]:
        symbol = (symbol or "").strip().upper()
        with self._lock:
            return self.by_symbol.get(symbol)

    def is_ready(self, symbol: str) -> bool:
        entry = self.get(symbol)
        return bool(entry and entry.ready)

    def is_loading(self, symbol: str) -> bool:
        entry = self.get(symbol)
        return bool(entry and entry.status == "loading")

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

        with self._lock:
            gen = self._generation.get(symbol, 0) + 1
            self._generation[symbol] = gen
            pending = NewsEnrichmentResult(symbol=symbol, status="loading", generation=gen)
            self.by_symbol[symbol] = pending

        self.root.after(0, lambda: self._notify(symbol, pending))

        def worker():
            def cancelled() -> bool:
                with self._lock:
                    return self._generation.get(symbol, 0) != gen

            result = enrich_symbol_news(
                symbol,
                company_name=company_name,
                limit=limit,
                should_cancel=cancelled,
            )
            result.generation = gen

            with self._lock:
                if self._generation.get(symbol, 0) != gen:
                    return
                self.by_symbol[symbol] = result

            self.root.after(0, lambda: self._notify(symbol, result))

        threading.Thread(target=worker, daemon=True).start()
