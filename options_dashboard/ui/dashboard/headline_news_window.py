"""
Dashboard Headline News window — preloaded LLM summaries + sentiment.
"""

from __future__ import annotations

import customtkinter as ctk

from data.news_enrichment import EnrichedArticle, NewsEnrichmentResult
from style.theme import ACCENT_PRIMARY, ACCENT_SUCCESS, TEXT_MUTED, TEXT_SECONDARY, get_fonts
from ui.dashboard.news_summary_window import open_enriched_article_window


def open_headline_news_window(
    parent,
    *,
    symbol: str,
    result: NewsEnrichmentResult,
) -> ctk.CTkToplevel:
    """List enriched headlines; click opens the preloaded LLM summary window."""
    fonts = get_fonts()
    symbol = (symbol or "").strip().upper() or "—"

    win = ctk.CTkToplevel(parent)
    win.title(f"Headline News — {symbol}")
    win.geometry("720x780")
    win.minsize(520, 480)
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

    count = len(result.articles)
    when = ""
    if result.fetched_at:
        when = result.fetched_at.astimezone().strftime("%I:%M:%S %p")
    meta_bits = [f"{count} article(s)"]
    if when:
        meta_bits.append(when)
    meta_bits.append("LLM summary + sentiment")

    ctk.CTkLabel(
        header,
        text="  ·  ".join(meta_bits),
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
    ).pack(fill="x", padx=16, pady=(0, 6))

    status_text = "Click a headline to open its summary."
    if result.errors:
        status_text = result.errors[-1]
    ctk.CTkLabel(
        header,
        text=status_text,
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
        wraplength=660,
        justify="left",
    ).pack(fill="x", padx=16, pady=(0, 12))

    body = ctk.CTkScrollableFrame(shell, corner_radius=12)
    body.pack(fill="both", expand=True)

    if not result.articles:
        ctk.CTkLabel(
            body,
            text="No articles available.",
            font=fonts["md"],
            text_color=TEXT_MUTED,
        ).pack(pady=40)
    else:
        for enriched in result.articles:
            _make_card(body, win, enriched, fonts)

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
            wraplength=640,
        ).pack(fill="x", padx=12, pady=(0, 10))
    else:
        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

    return card
