"""
Dashboard helpers for Headline News button state + enrichment kickoff.
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from data.news_enrichment import NewsEnrichmentController, NewsEnrichmentResult
from data.news_scraper import lookup_company_name
from style.theme import ACCENT_SUCCESS, TEXT_MUTED
from ui import dialogs
from ui.dashboard.headline_news_window import open_headline_news_window


def ensure_news_controller(dashboard) -> NewsEnrichmentController:
    if not hasattr(dashboard, "news_controller") or dashboard.news_controller is None:
        dashboard.news_controller = NewsEnrichmentController(dashboard.root)
        restored = getattr(dashboard, "_restored_news_by_symbol", None) or {}
        if restored:
            dashboard.news_controller.by_symbol.update(restored)
            dashboard._restored_news_by_symbol = {}
        dashboard.news_controller.add_listener(
            lambda _symbol, _entry: update_headline_news_button_state(dashboard)
        )
    return dashboard.news_controller


def resolve_dashboard_ticker(dashboard) -> Optional[str]:
    """Current single-view or selected multi-view ticker, or None."""
    is_single = (
        hasattr(dashboard, "single_view")
        and dashboard.single_view is not None
        and dashboard.single_view.winfo_viewable()
    )
    if is_single:
        symbol = getattr(dashboard, "single_view_symbol", None)
        if symbol and symbol != "_SINGLE_VIEW_PLACEHOLDER":
            return str(symbol).strip().upper()
        return None

    if hasattr(dashboard, "notebook") and dashboard.notebook:
        try:
            selected = dashboard.notebook.select()
            if selected:
                text = dashboard.notebook.tab(selected, "text").strip().upper()
                return text.replace(" (CSV)", "") or None
        except Exception:
            pass
    return None


def start_headline_news_enrichment(dashboard, symbol: str) -> None:
    """Kick off background news+LLM enrichment for a symbol."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return
    ctrl = ensure_news_controller(dashboard)
    company_name = lookup_company_name(symbol)
    ctrl.start(symbol, company_name=company_name)
    update_headline_news_button_state(dashboard, symbol=symbol)


def update_headline_news_button_state(dashboard, symbol: Optional[str] = None) -> None:
    """Enable Headline News only when enrichment for the current ticker is ready."""
    buttons = getattr(dashboard, "headline_news_buttons", None) or []
    dots = getattr(dashboard, "headline_news_dots", None) or []
    if not buttons and not dots:
        return

    current = (symbol or resolve_dashboard_ticker(dashboard) or "").strip().upper()
    ctrl = getattr(dashboard, "news_controller", None)
    entry: Optional[NewsEnrichmentResult] = ctrl.get(current) if ctrl and current else None

    ready = bool(entry and entry.ready)
    loading = bool(entry and entry.status == "loading")

    for btn in buttons:
        try:
            if not btn.winfo_exists():
                continue
            if ready:
                btn.configure(state="normal")
            else:
                btn.configure(state="disabled")
        except Exception:
            pass

    for dot in dots:
        try:
            if not dot.winfo_exists():
                continue
            if ready:
                dot.configure(text="●", text_color=ACCENT_SUCCESS)
            elif loading:
                dot.configure(text="●", text_color="#f59e0b")
            else:
                dot.configure(text="○", text_color=TEXT_MUTED)
        except Exception:
            pass


def open_headline_news_for_dashboard(dashboard) -> None:
    symbol = resolve_dashboard_ticker(dashboard)
    if not symbol:
        dialogs.warning("No Ticker", "Select or fetch a ticker first.")
        return

    ctrl = ensure_news_controller(dashboard)
    entry = ctrl.get(symbol)
    if not entry or not entry.ready:
        dialogs.warning(
            "News Still Loading",
            "Headline news is still being prepared.\n"
            "It runs automatically when you fetch options data.",
        )
        return

    open_headline_news_window(dashboard.root, symbol=symbol, result=entry)


def build_headline_news_control(parent, dashboard, *, width: int = 140) -> ctk.CTkFrame:
    """
    Build a Headline News button + ready-dot and register them on the dashboard.
    Returns the container frame (pack/place it yourself).
    """
    ensure_news_controller(dashboard)

    wrap = ctk.CTkFrame(parent, fg_color="transparent")

    btn = ctk.CTkButton(
        wrap,
        text="Headline News",
        width=width,
        state="disabled",
        command=lambda: open_headline_news_for_dashboard(dashboard),
    )
    btn.pack(side="left")

    dot = ctk.CTkLabel(
        wrap,
        text="○",
        width=18,
        text_color=TEXT_MUTED,
        font=ctk.CTkFont(size=16),
    )
    dot.pack(side="left", padx=(6, 0))

    if not hasattr(dashboard, "headline_news_buttons") or dashboard.headline_news_buttons is None:
        dashboard.headline_news_buttons = []
    if not hasattr(dashboard, "headline_news_dots") or dashboard.headline_news_dots is None:
        dashboard.headline_news_dots = []

    def _alive(w) -> bool:
        try:
            return bool(w.winfo_exists())
        except Exception:
            return False

    dashboard.headline_news_buttons = [b for b in dashboard.headline_news_buttons if _alive(b)]
    dashboard.headline_news_dots = [d for d in dashboard.headline_news_dots if _alive(d)]

    dashboard.headline_news_buttons.append(btn)
    dashboard.headline_news_dots.append(dot)

    update_headline_news_button_state(dashboard)
    return wrap
