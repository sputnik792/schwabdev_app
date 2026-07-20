"""
Standalone test UI for stock news scraping.

Run from the options_dashboard folder:
    python ml_features/test_news.py

Or from the repo root (with PYTHONPATH including options_dashboard):
    python options_dashboard/ml_features/test_news.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow imports like `data.*` / `style.*` / `ui.*` when run as a script
_OPTIONS_DASHBOARD = Path(__file__).resolve().parents[1]
_REPO_ROOT = _OPTIONS_DASHBOARD.parent
for path in (_OPTIONS_DASHBOARD, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import customtkinter as ctk

from style.custom_theme_controller import list_available_themes, set_color_theme
from style.theme import ACCENT_PRIMARY, TEXT_MUTED, get_fonts
from ui.dashboard.news_panel import NewsPanel


def main():
    ctk.set_appearance_mode("dark")

    themes = list_available_themes()
    set_color_theme(themes[0] if themes else "breeze")

    root = ctk.CTk()
    root.title("Stock News — Test")
    root.geometry("920x780")
    root.minsize(760, 520)

    fonts = get_fonts()

    shell = ctk.CTkFrame(root, fg_color="transparent")
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    # Top bar — mirrors dashboard control strip feel
    top = ctk.CTkFrame(shell, corner_radius=16)
    top.pack(fill="x", pady=(0, 12))

    ctk.CTkLabel(
        top,
        text="News Scraper Test",
        font=fonts["lg"],
    ).pack(side="left", padx=16, pady=14)

    controls = ctk.CTkFrame(top, fg_color="transparent")
    controls.pack(side="right", padx=12, pady=10)

    ctk.CTkLabel(controls, text="Ticker", font=fonts["sm"], text_color=TEXT_MUTED).pack(
        side="left", padx=(0, 6)
    )

    ticker_var = ctk.StringVar(value="AAPL")
    entry = ctk.CTkEntry(
        controls,
        textvariable=ticker_var,
        width=110,
        height=32,
        placeholder_text="e.g. AAPL",
    )
    entry.pack(side="left", padx=(0, 8))

    limit_var = ctk.StringVar(value="15")
    ctk.CTkLabel(controls, text="Limit", font=fonts["sm"], text_color=TEXT_MUTED).pack(
        side="left", padx=(4, 6)
    )
    limit_menu = ctk.CTkOptionMenu(
        controls,
        variable=limit_var,
        values=["5", "10", "15", "25"],
        width=70,
        height=32,
    )
    limit_menu.pack(side="left", padx=(0, 8))

    panel = NewsPanel(shell)
    panel.pack(fill="both", expand=True)

    def do_fetch(_event=None):
        symbol = ticker_var.get().strip().upper()
        try:
            limit = int(limit_var.get())
        except ValueError:
            limit = 15
        ticker_var.set(symbol)
        panel.fetch_async(symbol, limit=limit)

    fetch_btn = ctk.CTkButton(
        controls,
        text="Fetch News",
        width=110,
        height=32,
        fg_color=ACCENT_PRIMARY,
        command=do_fetch,
    )
    fetch_btn.pack(side="left")

    entry.bind("<Return>", do_fetch)

    hint = ctk.CTkLabel(
        shell,
        text="Click a headline → summary window (extractive, no LLM). Use Open in Browser inside that window for the full page.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    )
    hint.pack(fill="x", pady=(8, 0))

    # Auto-fetch once so the window isn't empty on launch
    root.after(250, do_fetch)

    root.mainloop()


if __name__ == "__main__":
    main()
