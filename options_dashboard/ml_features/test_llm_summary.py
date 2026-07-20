"""
Compare extractive vs local LLM (Ollama + SmolLM2) article summaries.

Prerequisites (one-time):
  1. Install Ollama: https://ollama.com/download
     or:  winget install Ollama.Ollama
  2. Pull SmolLM2:  ollama pull smollm2:1.7b
     (the test UI can also pull it for you on first run)

Run from options_dashboard:
    python ml_features/test_llm_summary.py
"""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

_OPTIONS_DASHBOARD = Path(__file__).resolve().parents[1]
_REPO_ROOT = _OPTIONS_DASHBOARD.parent
for path in (_OPTIONS_DASHBOARD, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import customtkinter as ctk

from data.article_summary import fetch_and_summarize, summarize_extractive
from data.news_scraper import NewsArticle, fetch_stock_news
from data.ollama_summarizer import (
    DEFAULT_MODEL,
    KNOWN_MODELS,
    check_ollama,
    ensure_model,
    summarize_with_ollama,
)
from style.custom_theme_controller import list_available_themes, set_color_theme
from style.theme import ACCENT_PRIMARY, ACCENT_SUCCESS, TEXT_MUTED, TEXT_SECONDARY, get_fonts
from ui.dashboard.news_summary_window import build_sentiment_indicator


def main():
    ctk.set_appearance_mode("dark")
    themes = list_available_themes()
    set_color_theme(themes[0] if themes else "breeze")

    root = ctk.CTk()
    root.title("LLM Summary Test — SmolLM2 via Ollama")
    root.geometry("980x820")
    root.minsize(780, 640)

    fonts = get_fonts()
    shell = ctk.CTkFrame(root, fg_color="transparent")
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    # ---- top bar ----
    top = ctk.CTkFrame(shell, corner_radius=16)
    top.pack(fill="x", pady=(0, 10))

    ctk.CTkLabel(top, text="Local LLM Summary Lab", font=fonts["lg"]).pack(
        side="left", padx=16, pady=14
    )

    controls = ctk.CTkFrame(top, fg_color="transparent")
    controls.pack(side="right", padx=12, pady=10)

    ctk.CTkLabel(controls, text="Ticker", font=fonts["sm"], text_color=TEXT_MUTED).pack(
        side="left", padx=(0, 6)
    )
    ticker_var = ctk.StringVar(value="AAPL")
    ticker_entry = ctk.CTkEntry(controls, textvariable=ticker_var, width=90, height=32)
    ticker_entry.pack(side="left", padx=(0, 8))

    ctk.CTkLabel(controls, text="Model", font=fonts["sm"], text_color=TEXT_MUTED).pack(
        side="left", padx=(4, 6)
    )
    model_var = ctk.StringVar(value=DEFAULT_MODEL)
    model_menu = ctk.CTkOptionMenu(
        controls, variable=model_var, values=KNOWN_MODELS, width=140, height=32
    )
    model_menu.pack(side="left", padx=(0, 8))

    # ---- status / setup strip ----
    status_frame = ctk.CTkFrame(shell, corner_radius=12)
    status_frame.pack(fill="x", pady=(0, 10))

    ollama_status = ctk.CTkLabel(
        status_frame,
        text="Checking Ollama…",
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
    )
    ollama_status.pack(fill="x", padx=14, pady=(10, 2))

    run_status = ctk.CTkLabel(
        status_frame,
        text="Fetch headlines, pick one, then Compare Summaries.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    )
    run_status.pack(fill="x", padx=14, pady=(0, 10))

    # ---- middle: headline list + article meta ----
    mid = ctk.CTkFrame(shell, fg_color="transparent")
    mid.pack(fill="both", expand=True)

    left = ctk.CTkFrame(mid, corner_radius=16)
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))

    ctk.CTkLabel(left, text="Headlines", font=fonts["md"], anchor="w").pack(
        fill="x", padx=14, pady=(12, 6)
    )

    headline_list = ctk.CTkScrollableFrame(left, corner_radius=10)
    headline_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    right = ctk.CTkFrame(mid, corner_radius=16, width=420)
    right.pack(side="right", fill="both", expand=True, padx=(8, 0))
    right.pack_propagate(False)

    selected_title = ctk.CTkLabel(
        right,
        text="No article selected",
        font=fonts["md"],
        anchor="w",
        justify="left",
        wraplength=380,
    )
    selected_title.pack(fill="x", padx=14, pady=(12, 4))

    selected_meta = ctk.CTkLabel(
        right,
        text="",
        font=fonts["sm"],
        text_color=TEXT_SECONDARY,
        anchor="w",
    )
    selected_meta.pack(fill="x", padx=14, pady=(0, 8))

    btn_row = ctk.CTkFrame(right, fg_color="transparent")
    btn_row.pack(fill="x", padx=14, pady=(0, 8))

    # ---- comparison panels ----
    compare = ctk.CTkFrame(shell, corner_radius=16)
    compare.pack(fill="both", expand=True, pady=(10, 0))

    cols = ctk.CTkFrame(compare, fg_color="transparent")
    cols.pack(fill="both", expand=True, padx=10, pady=10)

    extract_col = ctk.CTkFrame(cols, corner_radius=12)
    extract_col.pack(side="left", fill="both", expand=True, padx=(0, 6))
    ctk.CTkLabel(
        extract_col,
        text="Extractive (no LLM)",
        font=fonts["md"],
        text_color=ACCENT_PRIMARY,
        anchor="w",
    ).pack(fill="x", padx=10, pady=(10, 4))
    extract_meta = ctk.CTkLabel(
        extract_col, text="", font=fonts["sm"], text_color=TEXT_MUTED, anchor="w"
    )
    extract_meta.pack(fill="x", padx=10)
    extract_box = ctk.CTkTextbox(extract_col, wrap="word", font=fonts["sm"])
    extract_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    llm_col = ctk.CTkFrame(cols, corner_radius=12)
    llm_col.pack(side="right", fill="both", expand=True, padx=(6, 0))
    ctk.CTkLabel(
        llm_col,
        text="Local LLM (Ollama)",
        font=fonts["md"],
        text_color=ACCENT_SUCCESS,
        anchor="w",
    ).pack(fill="x", padx=10, pady=(10, 4))
    llm_meta = ctk.CTkLabel(
        llm_col, text="", font=fonts["sm"], text_color=TEXT_MUTED, anchor="w"
    )
    llm_meta.pack(fill="x", padx=10)
    sentiment_wrap, apply_sentiment = build_sentiment_indicator(llm_col, fonts=fonts)
    sentiment_wrap.pack(fill="x", padx=10, pady=(6, 2))
    apply_sentiment(None, "Run Compare Summaries for LLM sentiment.")
    llm_box = ctk.CTkTextbox(llm_col, wrap="word", font=fonts["sm"])
    llm_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    # ---- state ----
    articles: list[NewsArticle] = []
    selected: dict = {"article": None}
    headline_buttons: list[ctk.CTkButton] = []

    def set_box(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def refresh_ollama_status() -> None:
        st = check_ollama()
        if not st.reachable:
            ollama_status.configure(
                text=(
                    "Ollama offline — install from https://ollama.com/download "
                    "then reopen this window (or click Setup Model)."
                ),
                text_color="#f59e0b",
            )
            return
        model = model_var.get()
        has = any(m == model or m.startswith(model) for m in st.models)
        if has:
            ollama_status.configure(
                text=f"Ollama online · {len(st.models)} model(s) · ready: {model}",
                text_color=ACCENT_SUCCESS,
            )
        else:
            ollama_status.configure(
                text=f"Ollama online · {model} not pulled yet — click Setup Model",
                text_color="#f59e0b",
            )

    def clear_headlines() -> None:
        for btn in headline_buttons:
            btn.destroy()
        headline_buttons.clear()
        articles.clear()

    def select_article(article: NewsArticle) -> None:
        selected["article"] = article
        selected_title.configure(text=article.title)
        bits = [b for b in (article.source, article.published_label(), article.provider) if b]
        selected_meta.configure(text="  ·  ".join(bits))
        set_box(extract_box, "")
        set_box(llm_box, "")
        extract_meta.configure(text="")
        llm_meta.configure(text="")
        apply_sentiment(None, "Run Compare Summaries for LLM sentiment.")
        run_status.configure(text="Ready — click Compare Summaries.")

    def show_headlines(fetched: list[NewsArticle]) -> None:
        clear_headlines()
        articles.extend(fetched)
        if not fetched:
            empty = ctk.CTkLabel(
                headline_list, text="No headlines.", font=fonts["sm"], text_color=TEXT_MUTED
            )
            empty.pack(pady=20)
            headline_buttons.append(empty)  # type: ignore[arg-type]
            return
        for art in fetched:
            btn = ctk.CTkButton(
                headline_list,
                text=art.title[:110] + ("…" if len(art.title) > 110 else ""),
                anchor="w",
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                text_color=(ACCENT_PRIMARY, ACCENT_PRIMARY),
                height=36,
                command=lambda a=art: select_article(a),
            )
            btn.pack(fill="x", padx=4, pady=3)
            headline_buttons.append(btn)
        select_article(fetched[0])

    def do_fetch(_event=None) -> None:
        symbol = ticker_var.get().strip().upper()
        ticker_var.set(symbol)
        run_status.configure(text=f"Fetching headlines for {symbol}…")

        def worker():
            result = fetch_stock_news(symbol, limit=10)

            def apply():
                show_headlines(result.articles)
                if result.errors:
                    run_status.configure(
                        text=f"Loaded {len(result.articles)} · notes: {'; '.join(result.errors[:2])}"
                    )
                else:
                    run_status.configure(text=f"Loaded {len(result.articles)} headline(s).")

            root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def do_setup_model() -> None:
        model = model_var.get()
        run_status.configure(text=f"Pulling {model} (first time can take a few minutes)…")
        ollama_status.configure(text=f"Downloading {model}…", text_color="#f59e0b")

        def worker():
            err = ensure_model(model)

            def apply():
                refresh_ollama_status()
                if err:
                    run_status.configure(text=f"Setup failed: {err}")
                else:
                    run_status.configure(text=f"{model} is ready.")

            root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def do_compare() -> None:
        article: NewsArticle | None = selected["article"]
        if not article:
            run_status.configure(text="Select a headline first.")
            return

        model = model_var.get()
        run_status.configure(text="Downloading article + running both summarizers…")
        set_box(extract_box, "Loading…")
        set_box(llm_box, "Waiting for extract, then calling Ollama…")
        extract_meta.configure(text="")
        llm_meta.configure(text="")
        apply_sentiment(None, "Analyzing sentiment…")

        def worker():
            t0 = time.perf_counter()
            content = fetch_and_summarize(
                article.link,
                title_hint=article.title,
                rss_fallback=article.summary or "",
                max_sentences=5,
            )
            extract_elapsed = time.perf_counter() - t0

            # Recompute extractive on full text so timing is fair/clear
            if content.text:
                ext_summary, n_sent = summarize_extractive(content.text, max_sentences=5)
            else:
                ext_summary, n_sent = content.summary, content.sentences_used

            llm = summarize_with_ollama(
                content.text or content.summary,
                title=content.title or article.title,
                model=model,
            )

            def apply():
                set_box(extract_box, ext_summary or "(empty)")
                extract_meta.configure(
                    text=f"{n_sent} sentences · {extract_elapsed:.1f}s · {len(content.text)} chars extracted"
                )

                if llm.ok:
                    set_box(llm_box, llm.summary)
                    llm_meta.configure(
                        text=f"{llm.model} · {llm.elapsed_sec:.1f}s · prompt {llm.prompt_chars} chars"
                    )
                    if llm.sentiment and llm.sentiment.ok:
                        apply_sentiment(llm.sentiment)
                    elif llm.sentiment:
                        apply_sentiment(llm.sentiment, status=llm.sentiment.error or "Parse failed")
                    else:
                        apply_sentiment(None, "No sentiment in model response.")
                else:
                    set_box(llm_box, llm.error or "LLM summary failed.")
                    llm_meta.configure(text=f"{model} · failed")
                    apply_sentiment(None, llm.error or "LLM failed")

                if llm.ok and not content.errors:
                    run_status.configure(text="Done — compare the two summaries side by side.")
                elif llm.ok:
                    run_status.configure(text=f"Done (notes: {content.errors[-1][:80]})")
                else:
                    run_status.configure(
                        text="Extractive OK; LLM failed — is Ollama running and model pulled?"
                    )

                bits = [b for b in (article.source, article.published_label(), article.provider) if b]
                if content.final_url:
                    bits.append(content.final_url[:70])
                selected_meta.configure(text="  ·  ".join(bits))

            root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def open_article() -> None:
        article = selected["article"]
        if article:
            webbrowser.open(article.link)

    fetch_btn = ctk.CTkButton(
        controls, text="Fetch", width=80, height=32, fg_color=ACCENT_PRIMARY, command=do_fetch
    )
    fetch_btn.pack(side="left")

    setup_btn = ctk.CTkButton(
        btn_row, text="Setup Model", width=110, height=32, command=do_setup_model
    )
    setup_btn.pack(side="left", padx=(0, 8))

    compare_btn = ctk.CTkButton(
        btn_row,
        text="Compare Summaries",
        width=150,
        height=32,
        fg_color=ACCENT_PRIMARY,
        command=do_compare,
    )
    compare_btn.pack(side="left", padx=(0, 8))

    open_btn = ctk.CTkButton(
        btn_row,
        text="Open Article",
        width=110,
        height=32,
        fg_color="transparent",
        border_width=1,
        command=open_article,
    )
    open_btn.pack(side="left")

    ticker_entry.bind("<Return>", do_fetch)
    model_menu.configure(command=lambda _v: refresh_ollama_status())

    hint = ctk.CTkLabel(
        shell,
        text="Default model: smollm2:1.7b via Ollama (lowest RAM). Also try phi3:mini / qwen2.5:3b from the dropdown.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    )
    hint.pack(fill="x", pady=(8, 0))

    root.after(200, refresh_ollama_status)
    root.after(400, do_fetch)
    root.mainloop()


if __name__ == "__main__":
    main()
