"""
Toplevel window that shows an extractive summary of a news article,
plus an LLM market-sentiment badge (very bearish → very bullish).
"""

from __future__ import annotations

import threading
import webbrowser
from typing import Callable, Optional, Tuple

import customtkinter as ctk

from data.article_summary import ArticleContent, fetch_and_summarize
from data.news_scraper import NewsArticle
from data.ollama_summarizer import (
    SENTIMENT_LABELS,
    SENTIMENT_META,
    SentimentResult,
    analyze_sentiment_with_ollama,
    check_ollama,
)
from style.theme import ACCENT_PRIMARY, TEXT_MUTED, TEXT_SECONDARY, get_fonts

# Min content width for news windows — narrower views get a horizontal scrollbar.
NEWS_CONTENT_WIDTH = 760


def create_xy_scrollable_frame(
    master,
    *,
    content_width: int = NEWS_CONTENT_WIDTH,
    corner_radius: int = 12,
) -> ctk.CTkScrollableFrame:
    """
    Nested scroll area: vertical list + horizontal overflow.

    Returns the inner vertical CTkScrollableFrame — pack content into it.
    """
    horizontal = ctk.CTkScrollableFrame(
        master,
        orientation="horizontal",
        corner_radius=corner_radius,
    )
    horizontal.pack(fill="both", expand=True)

    vertical = ctk.CTkScrollableFrame(
        horizontal,
        orientation="vertical",
        width=content_width,
        corner_radius=corner_radius,
    )
    vertical.pack(side="left", fill="y", expand=True)
    return vertical


def build_sentiment_indicator(
    parent,
    *,
    fonts=None,
) -> Tuple[ctk.CTkFrame, Callable[[Optional[SentimentResult], str], None]]:
    """
    Build a 5-stop sentiment bar + badge. Returns (frame, apply_fn).

    apply_fn(sentiment, status="") updates the UI.
    Pass sentiment=None to show a loading/unavailable state with status text.
    """
    fonts = fonts or get_fonts()
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    header = ctk.CTkFrame(frame, fg_color="transparent")
    header.pack(fill="x")

    title = ctk.CTkLabel(
        header,
        text="Market sentiment",
        font=fonts["md"],
        text_color=ACCENT_PRIMARY,
        anchor="w",
    )
    title.pack(side="left")

    badge = ctk.CTkLabel(
        header,
        text="Analyzing…",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        fg_color=("gray85", "gray25"),
        corner_radius=8,
        padx=10,
        pady=3,
    )
    badge.pack(side="right")

    # Five-stop gradient bar (very bearish → very bullish)
    bar = ctk.CTkFrame(frame, fg_color="transparent")
    bar.pack(fill="x", pady=(8, 2))

    stops: list[ctk.CTkFrame] = []
    for i, label in enumerate(SENTIMENT_LABELS):
        color = SENTIMENT_META[label][1]
        stop = ctk.CTkFrame(bar, width=48, height=10, corner_radius=4, fg_color=color)
        stop.pack(side="left", padx=(0 if i == 0 else 3, 0), fill="x", expand=True)
        stop.pack_propagate(False)
        stops.append(stop)

    scale = ctk.CTkFrame(frame, fg_color="transparent")
    scale.pack(fill="x")
    ctk.CTkLabel(
        scale,
        text="Very Bearish",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    ).pack(side="left")
    ctk.CTkLabel(
        scale,
        text="Very Bullish",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="e",
    ).pack(side="right")

    reason_label = ctk.CTkLabel(
        frame,
        text="",
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
        justify="left",
        wraplength=560,
    )
    reason_label.pack(fill="x", pady=(6, 0))

    def _dim_stops(active_index: Optional[int]) -> None:
        for i, stop in enumerate(stops):
            base = SENTIMENT_META[SENTIMENT_LABELS[i]][1]
            if active_index is None:
                stop.configure(fg_color=base, height=8)
            elif i == active_index:
                stop.configure(fg_color=base, height=14)
            else:
                # Mute non-selected stops
                stop.configure(fg_color=("gray75", "gray35"), height=8)

    def apply(sentiment: Optional[SentimentResult], status: str = "") -> None:
        if sentiment is None:
            badge.configure(
                text=status or "Unavailable",
                text_color=TEXT_MUTED,
                fg_color=("gray85", "gray25"),
            )
            reason_label.configure(text=status if status and "…" not in status else "")
            _dim_stops(None)
            return

        if not sentiment.ok:
            badge.configure(
                text=status or (sentiment.error[:48] if sentiment.error else "Failed"),
                text_color=TEXT_MUTED,
                fg_color=("gray85", "gray25"),
            )
            reason_label.configure(text=sentiment.error or status)
            _dim_stops(None)
            return

        badge.configure(
            text=sentiment.display_label,
            text_color="#ffffff",
            fg_color=sentiment.color,
        )
        reason = sentiment.reason.strip()
        if reason:
            reason_label.configure(text=reason)
        else:
            reason_label.configure(text=status or "")
        _dim_stops(sentiment.index)

    return frame, apply


def open_article_summary_window(
    parent,
    article: NewsArticle,
    *,
    max_sentences: int = 5,
) -> ctk.CTkToplevel:
    """Open a summary window and load article content in a background thread."""
    fonts = get_fonts()

    win = ctk.CTkToplevel(parent)
    title_preview = (article.title or "Article")[:80]
    win.title(f"Summary — {title_preview}")
    win.geometry("880x780")
    win.minsize(700, 520)
    win.transient(parent)
    win.lift()
    win.focus()

    shell = ctk.CTkFrame(win, fg_color="transparent")
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    header = ctk.CTkFrame(shell, corner_radius=16)
    header.pack(fill="x", pady=(0, 12))

    title_label = ctk.CTkLabel(
        header,
        text=article.title or "Loading article…",
        font=fonts["lg"],
        anchor="w",
        justify="left",
        wraplength=560,
    )
    title_label.pack(fill="x", padx=16, pady=(14, 4))

    meta_bits = [b for b in (article.source, article.published_label()) if b]
    meta_label = ctk.CTkLabel(
        header,
        text="  ·  ".join(meta_bits) if meta_bits else "Fetching page…",
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
    )
    meta_label.pack(fill="x", padx=16, pady=(0, 6))

    status_label = ctk.CTkLabel(
        header,
        text="Downloading and summarizing…",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    )
    status_label.pack(fill="x", padx=16, pady=(0, 12))

    body_host = ctk.CTkFrame(shell, fg_color="transparent")
    body_host.pack(fill="both", expand=True)
    body = create_xy_scrollable_frame(body_host, corner_radius=12)

    sentiment_frame, apply_sentiment = build_sentiment_indicator(body, fonts=fonts)
    sentiment_frame.pack(fill="x", padx=8, pady=(8, 4))
    apply_sentiment(None, "Waiting for article…")

    section_summary = ctk.CTkLabel(
        body,
        text="Summary",
        font=fonts["md"],
        text_color=ACCENT_PRIMARY,
        anchor="w",
    )
    section_summary.pack(fill="x", padx=8, pady=(12, 4))

    summary_box = ctk.CTkTextbox(body, height=200, wrap="word", font=fonts["md"])
    summary_box.pack(fill="x", padx=8, pady=(0, 12))
    summary_box.insert("1.0", "Loading…")
    summary_box.configure(state="disabled")

    section_full = ctk.CTkLabel(
        body,
        text="Extracted article text",
        font=fonts["md"],
        text_color=ACCENT_PRIMARY,
        anchor="w",
    )
    section_full.pack(fill="x", padx=8, pady=(4, 4))

    full_box = ctk.CTkTextbox(body, height=260, wrap="word", font=fonts["sm"])
    full_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    full_box.insert("1.0", "Loading…")
    full_box.configure(state="disabled")

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.pack(fill="x", pady=(10, 0))

    open_btn = ctk.CTkButton(
        footer,
        text="Open in Browser",
        width=140,
        height=32,
        fg_color=ACCENT_PRIMARY,
        command=lambda: webbrowser.open(article.link),
        state="normal",
    )
    open_btn.pack(side="left")

    close_btn = ctk.CTkButton(
        footer,
        text="Close",
        width=90,
        height=32,
        fg_color="transparent",
        border_width=1,
        command=win.destroy,
    )
    close_btn.pack(side="right")

    def set_textbox(box: ctk.CTkTextbox, value: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", value)
        box.configure(state="disabled")

    def apply_result(content: ArticleContent) -> None:
        if content.title:
            title_label.configure(text=content.title)
            win.title(f"Summary — {content.title[:80]}")

        host = content.final_url
        meta_label.configure(
            text=(
                "  ·  ".join(meta_bits + [host])
                if meta_bits
                else host
            )
        )

        if content.summary:
            set_textbox(summary_box, content.summary)
            note = f"Extractive summary · {content.sentences_used} key sentence(s)"
            if content.errors:
                note += "  ·  " + content.errors[-1]
            status_label.configure(text=note)
        else:
            err = "; ".join(content.errors) or "No summary available."
            set_textbox(summary_box, err)
            status_label.configure(text=err)

        if content.text:
            set_textbox(full_box, content.text)
        else:
            set_textbox(
                full_box,
                "; ".join(content.errors)
                or "Could not extract article body from this page.",
            )

        open_btn.configure(command=lambda u=content.final_url or article.link: webbrowser.open(u))

    def apply_sentiment_result(sentiment: SentimentResult) -> None:
        if sentiment.ok:
            apply_sentiment(sentiment)
        else:
            apply_sentiment(sentiment, status=sentiment.error or "Sentiment unavailable")

    def worker():
        content = fetch_and_summarize(
            article.link,
            title_hint=article.title,
            rss_fallback=article.summary or "",
            max_sentences=max_sentences,
        )
        win.after(0, lambda: apply_result(content))

        text_for_sentiment = content.text or content.summary or article.summary or ""
        if not text_for_sentiment.strip():
            win.after(
                0,
                lambda: apply_sentiment(None, "No article text for sentiment analysis."),
            )
            return

        win.after(0, lambda: apply_sentiment(None, "Running LLM sentiment…"))
        status = check_ollama()
        if not status.reachable:
            win.after(
                0,
                lambda: apply_sentiment(
                    None,
                    "Ollama offline — start Ollama to enable sentiment.",
                ),
            )
            return

        sentiment = analyze_sentiment_with_ollama(
            text_for_sentiment,
            title=content.title or article.title,
        )
        win.after(0, lambda: apply_sentiment_result(sentiment))

    threading.Thread(target=worker, daemon=True).start()
    return win


def open_enriched_article_window(parent, enriched) -> ctk.CTkToplevel:
    """
    Open a preloaded LLM summary + sentiment window (no extractive path).
    `enriched` is a data.news_enrichment.EnrichedArticle.
    """
    fonts = get_fonts()
    article = enriched.article
    title = enriched.display_title

    win = ctk.CTkToplevel(parent)
    win.title(f"Summary — {title[:80]}")
    win.geometry("880x720")
    win.minsize(700, 480)
    win.transient(parent)
    win.lift()
    win.focus()

    shell = ctk.CTkFrame(win, fg_color="transparent")
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    header = ctk.CTkFrame(shell, corner_radius=16)
    header.pack(fill="x", pady=(0, 12))

    ctk.CTkLabel(
        header,
        text=title,
        font=fonts["lg"],
        anchor="w",
        justify="left",
        wraplength=560,
    ).pack(fill="x", padx=16, pady=(14, 4))

    meta_bits = [b for b in (article.source, article.published_label(), enriched.open_url) if b]
    ctk.CTkLabel(
        header,
        text="  ·  ".join(meta_bits),
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
        wraplength=560,
        justify="left",
    ).pack(fill="x", padx=16, pady=(0, 6))

    ctk.CTkLabel(
        header,
        text="Local LLM summary + market sentiment",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    ).pack(fill="x", padx=16, pady=(0, 12))

    body_host = ctk.CTkFrame(shell, fg_color="transparent")
    body_host.pack(fill="both", expand=True)
    body = create_xy_scrollable_frame(body_host, corner_radius=12)

    sentiment_frame, apply_sentiment = build_sentiment_indicator(body, fonts=fonts)
    sentiment_frame.pack(fill="x", padx=8, pady=(8, 4))
    if enriched.sentiment and enriched.sentiment.ok:
        apply_sentiment(enriched.sentiment)
    elif enriched.sentiment:
        apply_sentiment(enriched.sentiment, status=enriched.sentiment.error or "Unavailable")
    else:
        apply_sentiment(None, enriched.error or "Sentiment unavailable")

    ctk.CTkLabel(
        body,
        text="LLM Summary",
        font=fonts["md"],
        text_color=ACCENT_PRIMARY,
        anchor="w",
    ).pack(fill="x", padx=8, pady=(12, 4))

    summary_box = ctk.CTkTextbox(body, height=280, wrap="word", font=fonts["md"])
    summary_box.pack(fill="both", expand=True, padx=8, pady=(0, 12))
    summary_text = enriched.llm_summary.strip() if enriched.llm_summary else (
        enriched.error or "No LLM summary available for this article."
    )
    summary_box.insert("1.0", summary_text)
    summary_box.configure(state="disabled")

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.pack(fill="x", pady=(10, 0))

    ctk.CTkButton(
        footer,
        text="Open in Browser",
        width=140,
        height=32,
        fg_color=ACCENT_PRIMARY,
        command=lambda: webbrowser.open(enriched.open_url or article.link),
    ).pack(side="left")

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
