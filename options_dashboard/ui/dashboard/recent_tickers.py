"""
Recent ticker shortcut buttons — fills the ticker entry when clicked.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Tuple

import customtkinter as ctk

from data.ticker_history import RECENT_TICKER_LIMIT, get_recent_tickers
from style.theme import TEXT_MUTED, get_fonts


def build_recent_ticker_bar(
    parent,
    ticker_var: tk.StringVar,
    *,
    on_select: Optional[Callable[[str], None]] = None,
) -> Tuple[ctk.CTkFrame, Callable[[], None]]:
    """
    Build a 'Recent' row of shortcut buttons above a ticker entry.

    Returns (container_frame, refresh_fn).
    """
    fonts = get_fonts()
    container = ctk.CTkFrame(parent, fg_color="transparent")

    ctk.CTkLabel(
        container,
        text="Recent",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        anchor="w",
    ).pack(fill="x", padx=16, pady=(0, 4))

    buttons_row = ctk.CTkFrame(container, fg_color="transparent")
    buttons_row.pack(fill="x", padx=12, pady=(0, 6))

    def _select(symbol: str) -> None:
        ticker_var.set(symbol)
        if on_select:
            on_select(symbol)

    def refresh() -> None:
        for widget in buttons_row.winfo_children():
            widget.destroy()

        recent = get_recent_tickers(RECENT_TICKER_LIMIT)
        if not recent:
            ctk.CTkLabel(
                buttons_row,
                text="—",
                font=fonts["sm"],
                text_color=TEXT_MUTED,
                anchor="w",
            ).pack(side="left", padx=4)
            return

        for symbol in recent:
            ctk.CTkButton(
                buttons_row,
                text=symbol,
                width=52,
                height=28,
                font=fonts["sm"],
                fg_color=("gray80", "gray28"),
                hover_color=("gray70", "gray35"),
                command=lambda s=symbol: _select(s),
            ).pack(side="left", padx=3)

    refresh()
    return container, refresh
