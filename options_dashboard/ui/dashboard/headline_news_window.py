"""
Dashboard Headline News window — preloaded LLM summaries + sentiment.

Shows cached articles immediately and appends newly scraped ones as refresh finishes.
"""

from __future__ import annotations

import webbrowser
from typing import Optional, Set

import customtkinter as ctk

from data.news_cache import article_identity
from data.news_enrichment import EnrichedArticle, NewsEnrichmentController, NewsEnrichmentResult
from data.news_scraper import format_local_datetime
from style.theme import ACCENT_PRIMARY, ACCENT_SUCCESS, TEXT_MUTED, TEXT_SECONDARY, get_fonts
from ui.dashboard.news_summary_window import (
    NEWS_CONTENT_WIDTH,
    create_xy_scrollable_frame,
    open_enriched_article_window,
)


def open_headline_news_window(
    parent,
    *,
    symbol: str,
    result: NewsEnrichmentResult,
    controller: Optional[NewsEnrichmentController] = None,
) -> ctk.CTkToplevel:
    """List enriched headlines; click opens the preloaded LLM summary window."""
    fonts = get_fonts()
    symbol = (symbol or "").strip().upper() or "—"

    win = ctk.CTkToplevel(parent)
    win.title(f"Headline News — {symbol}")
    win.geometry("920x780")
    win.minsize(760, 520)
    win.transient(parent)
    win.lift()
    win.focus()

    shell = ctk.CTkFrame(win, fg_color="transparent")
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    header = ctk.CTkFrame(shell, corner_radius=16)
    header.pack(fill="x", pady=(0, 12))

    ctk.CTkLabel(
        header,
        text=f"{symbol}  ·  Headline News",
        font=fonts["lg"],
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 4))

    meta_label = ctk.CTkLabel(
        header,
        text="",
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
    )
    meta_label.pack(fill="x", padx=16, pady=(0, 6))

    status_label = ctk.CTkLabel(
        header,
        text="",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
        wraplength=NEWS_CONTENT_WIDTH - 40,
        justify="left",
    )
    status_label.pack(fill="x", padx=16, pady=(0, 12))

    body_host = ctk.CTkFrame(shell, fg_color="transparent")
    body_host.pack(fill="both", expand=True)
    body = create_xy_scrollable_frame(body_host, corner_radius=12)

    empty_label = ctk.CTkLabel(
        body,
        text="No articles available yet — searching…",
        font=fonts["md"],
        text_color=TEXT_MUTED,
    )

    shown_keys: Set[str] = set()

    def _update_header(entry: NewsEnrichmentResult) -> None:
        count = len(entry.articles)
        when = ""
        if entry.fetched_at:
            when = format_local_datetime(entry.fetched_at, fmt="%I:%M:%S %p")
        meta_bits = [f"{count} article(s)"]
        if when:
            meta_bits.append(when)
        if entry.is_refreshing or entry.status == "loading":
            meta_bits.append("searching for updates…")
        elif entry.from_cache:
            meta_bits.append("loaded from cache")
        else:
            meta_bits.append("LLM summary + sentiment")
        meta_label.configure(text="  ·  ".join(meta_bits))

        if entry.is_refreshing or entry.status == "loading":
            status_label.configure(
                text="Showing saved articles while the scraper looks for new headlines…"
            )
        elif entry.new_articles:
            n = len(entry.new_articles)
            status_label.configure(
                text=f"Added {n} new article(s). Click a headline for its summary."
            )
        elif entry.errors:
            status_label.configure(text=entry.errors[-1])
        else:
            status_label.configure(text="Click a headline to open its summary.")

    def _ensure_empty_state(has_articles: bool) -> None:
        try:
            if has_articles:
                empty_label.pack_forget()
            else:
                empty_label.pack(pady=40)
        except Exception:
            pass

    def _prepend_card(enriched: EnrichedArticle) -> None:
        key = article_identity(enriched)
        if not key or key in shown_keys:
            return
        shown_keys.add(key)
        _ensure_empty_state(True)
        card = _make_card(body, win, enriched, fonts)
        # Move newest cards to the top of the scroll area
        try:
            card.pack_forget()
            children = [w for w in body.winfo_children() if w is not empty_label]
            if children:
                card.pack(fill="x", padx=4, pady=6, before=children[0])
            else:
                card.pack(fill="x", padx=4, pady=6)
        except Exception:
            card.pack(fill="x", padx=4, pady=6)

    def _render_initial(entry: NewsEnrichmentResult) -> None:
        for child in list(body.winfo_children()):
            if child is empty_label:
                continue
            try:
                child.destroy()
            except Exception:
                pass
        shown_keys.clear()
        if not entry.articles:
            _ensure_empty_state(False)
        else:
            _ensure_empty_state(True)
            # Articles are newest-first; pack in order
            for enriched in entry.articles:
                key = article_identity(enriched)
                if not key or key in shown_keys:
                    continue
                shown_keys.add(key)
                _make_card(body, win, enriched, fonts)
        _update_header(entry)

    def _on_news_update(sym: str, entry: NewsEnrichmentResult) -> None:
        if (sym or "").strip().upper() != symbol:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return

        def apply():
            try:
                if not win.winfo_exists():
                    return
            except Exception:
                return
            # Prefer appending only true newcomers when available
            newcomers = list(entry.new_articles or [])
            if newcomers:
                # new_articles is newest-first; prepend in reverse so final top order is newest-first
                for enriched in reversed(newcomers):
                    _prepend_card(enriched)
            elif entry.articles and not shown_keys:
                _render_initial(entry)
            elif entry.articles:
                for enriched in reversed(entry.articles):
                    _prepend_card(enriched)
            _update_header(entry)

        win.after(0, apply)

    _render_initial(result)

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.pack(fill="x", pady=(10, 0))
    ctk.CTkButton(
        footer,
        text="Close",
        width=90,
        height=32,
        fg_color="transparent",
        border_width=1,
        command=win.destroy,
    ).pack(side="right")

    if controller is not None:
        controller.add_listener(_on_news_update)

        def _cleanup(*_args):
            controller.remove_listener(_on_news_update)

        win.bind("<Destroy>", _cleanup)

    return win


def _make_card(parent, win, enriched: EnrichedArticle, fonts) -> ctk.CTkFrame:
    card = ctk.CTkFrame(parent, corner_radius=12)
    card.pack(fill="x", padx=4, pady=6)

    top = ctk.CTkFrame(card, fg_color="transparent")
    top.pack(fill="x", padx=12, pady=(10, 2))

    source = enriched.article.source or enriched.article.provider.replace("_", " ").title()
    when = enriched.article.published_label()
    meta_bits = [b for b in (source, when) if b]
    meta = "  ·  ".join(meta_bits)

    ctk.CTkLabel(
        top,
        text=meta or "News",
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
    ).pack(side="left", fill="x", expand=True)

    if enriched.sentiment and enriched.sentiment.ok:
        ctk.CTkLabel(
            top,
            text=enriched.sentiment.display_label,
            font=fonts["sm"],
            text_color="#ffffff",
            fg_color=enriched.sentiment.color,
            corner_radius=8,
            padx=8,
            pady=2,
        ).pack(side="right")
    elif enriched.llm_summary:
        ctk.CTkLabel(
            top,
            text="Summary ready",
            font=fonts["sm"],
            text_color=ACCENT_SUCCESS,
            anchor="e",
        ).pack(side="right")

    ctk.CTkButton(
        card,
        text=enriched.display_title,
        font=fonts["md"],
        anchor="w",
        fg_color="transparent",
        hover_color=("gray85", "gray25"),
        text_color=(ACCENT_PRIMARY, ACCENT_PRIMARY),
        command=lambda e=enriched: open_enriched_article_window(win, e),
    ).pack(fill="x", padx=8, pady=(0, 4))

    actions = ctk.CTkFrame(card, fg_color="transparent")
    actions.pack(fill="x", padx=12, pady=(0, 4))

    ctk.CTkLabel(
        actions,
        text="Click headline for LLM summary",
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
        command=lambda url=enriched.open_url: webbrowser.open(url),
    ).pack(side="right")

    preview = (enriched.llm_summary or enriched.article.summary or enriched.error or "").strip()
    if preview:
        if len(preview) > 220:
            preview = preview[:217].rstrip() + "..."
        ctk.CTkLabel(
            card,
            text=preview,
            font=fonts["sm"],
            text_color=TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=NEWS_CONTENT_WIDTH - 40,
        ).pack(fill="x", padx=12, pady=(0, 10))
    else:
        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

    return card
