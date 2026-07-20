"""
Reusable news panel UI for ticker headlines.

Used by the standalone news test window and (later) the main dashboard.
"""

from __future__ import annotations

import threading
import webbrowser
from typing import Callable, List, Optional

import customtkinter as ctk

from data.news_scraper import NewsArticle, NewsFetchResult, fetch_stock_news, format_local_datetime
from style.theme import ACCENT_PRIMARY, TEXT_MUTED, TEXT_SECONDARY, get_fonts
from ui.dashboard.news_summary_window import (
    NEWS_CONTENT_WIDTH,
    create_xy_scrollable_frame,
    open_article_summary_window,
)


class NewsPanel(ctk.CTkFrame):
    """Scrollable list of news cards for a given ticker."""

    def __init__(
        self,
        master,
        *,
        on_status: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, corner_radius=16, **kwargs)
        self._on_status = on_status
        self._fetch_token = 0
        self._article_frames: List[ctk.CTkFrame] = []

        fonts = get_fonts()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        self.title_label = ctk.CTkLabel(
            header,
            text="Stock News",
            font=fonts["lg"],
            anchor="w",
        )
        self.title_label.pack(side="left")

        self.meta_label = ctk.CTkLabel(
            header,
            text="",
            font=fonts["sm"],
            text_color=TEXT_SECONDARY,
            anchor="e",
        )
        self.meta_label.pack(side="right")

        self.status_label = ctk.CTkLabel(
            self,
            text="Enter a ticker and click Fetch News.",
            font=fonts["sm"],
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=16, pady=(0, 8))

        list_host = ctk.CTkFrame(self, fg_color="transparent")
        list_host.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.list_frame = create_xy_scrollable_frame(list_host, corner_radius=12)

        empty = ctk.CTkLabel(
            self.list_frame,
            text="No articles yet.",
            font=fonts["md"],
            text_color=TEXT_MUTED,
        )
        empty.pack(pady=40)
        self._empty_label = empty

    def set_status(self, text: str) -> None:
        self.status_label.configure(text=text)
        if self._on_status:
            self._on_status(text)

    def clear_articles(self) -> None:
        for frame in self._article_frames:
            frame.destroy()
        self._article_frames.clear()
        if self._empty_label.winfo_exists():
            self._empty_label.pack(pady=40)

    def show_articles(self, result: NewsFetchResult) -> None:
        self.clear_articles()
        if self._empty_label.winfo_exists():
            self._empty_label.pack_forget()

        symbol = result.symbol or "—"
        self.title_label.configure(text=f"{symbol}  ·  News")
        count = len(result.articles)
        fetched = format_local_datetime(result.fetched_at, fmt="%I:%M:%S %p")
        self.meta_label.configure(text=f"{count} articles  ·  {fetched}")

        if not result.articles:
            err = "; ".join(result.errors) if result.errors else "No articles found."
            self.set_status(err)
            empty = ctk.CTkLabel(
                self.list_frame,
                text=err,
                font=get_fonts()["md"],
                text_color=TEXT_MUTED,
            )
            empty.pack(pady=40)
            self._article_frames.append(empty)  # type: ignore[arg-type]
            return

        warn = ""
        if result.errors:
            warn = f"  (partial: {len(result.errors)} source issue(s))"
        self.set_status(f"Loaded {count} article(s) for {symbol}.{warn}")

        for article in result.articles:
            self._article_frames.append(self._make_card(article))

    def _make_card(self, article: NewsArticle) -> ctk.CTkFrame:
        fonts = get_fonts()
        card = ctk.CTkFrame(self.list_frame, corner_radius=12)
        card.pack(fill="x", padx=4, pady=6)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 2))

        source = article.source or article.provider.replace("_", " ").title()
        when = article.published_label()
        meta_bits = [b for b in (source, when) if b]
        meta = "  ·  ".join(meta_bits)

        ctk.CTkLabel(
            top,
            text=meta,
            font=fonts["sm"],
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x")

        title_btn = ctk.CTkButton(
            card,
            text=article.title,
            font=fonts["md"],
            anchor="w",
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=(ACCENT_PRIMARY, ACCENT_PRIMARY),
            command=lambda a=article: open_article_summary_window(
                self.winfo_toplevel(), a
            ),
        )
        title_btn.pack(fill="x", padx=8, pady=(0, 2))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(
            actions,
            text="Click headline for summary + LLM sentiment",
            font=fonts["sm"],
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="Open",
            width=72,
            height=28,
            font=fonts["sm"],
            fg_color="transparent",
            border_width=1,
            command=lambda url=article.link: webbrowser.open(url),
        ).pack(side="right")

        if article.summary:
            summary = article.summary
            if len(summary) > 220:
                summary = summary[:217].rstrip() + "..."
            ctk.CTkLabel(
                card,
                text=summary,
                font=fonts["sm"],
                text_color=TEXT_MUTED,
                anchor="w",
                justify="left",
                wraplength=NEWS_CONTENT_WIDTH - 40,
            ).pack(fill="x", padx=12, pady=(0, 10))
        else:
            ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

        return card

    def fetch_async(
        self,
        symbol: str,
        *,
        company_name: str = "",
        limit: int = 15,
        after: Optional[Callable[[NewsFetchResult], None]] = None,
    ) -> None:
        symbol = (symbol or "").upper().strip()
        if not symbol:
            self.set_status("Enter a ticker symbol first.")
            return

        self._fetch_token += 1
        token = self._fetch_token
        self.set_status(f"Fetching news for {symbol}...")
        self.clear_articles()
        loading = ctk.CTkLabel(
            self.list_frame,
            text="Loading…",
            font=get_fonts()["md"],
            text_color=TEXT_MUTED,
        )
        loading.pack(pady=40)
        self._article_frames.append(loading)  # type: ignore[arg-type]

        root = self.winfo_toplevel()

        def worker():
            result = fetch_stock_news(symbol, company_name=company_name, limit=limit)

            def apply():
                if token != self._fetch_token:
                    return
                self.show_articles(result)
                if after:
                    after(result)

            root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()
