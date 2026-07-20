"""
Dashboard helpers for Headline News button state + enrichment kickoff.
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from data.news_enrichment import NewsEnrichmentController, NewsEnrichmentResult
from data.news_cache import load_news_cache
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
    """Kick off background news+LLM enrichment for a symbol (loads cache first)."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return
    ctrl = ensure_news_controller(dashboard)
    company_name = lookup_company_name(symbol)
    ctrl.start(symbol, company_name=company_name)
    update_headline_news_button_state(dashboard, symbol=symbol)


def update_headline_news_button_state(dashboard, symbol: Optional[str] = None) -> None:
    """Enable Headline News when cache/memory has articles (even while refreshing)."""
    buttons = getattr(dashboard, "headline_news_buttons", None) or []
    dots = getattr(dashboard, "headline_news_dots", None) or []
    if not buttons and not dots:
        return

    current = (symbol or resolve_dashboard_ticker(dashboard) or "").strip().upper()
    ctrl = getattr(dashboard, "news_controller", None)
    entry: Optional[NewsEnrichmentResult] = ctrl.get(current) if ctrl and current else None

    # Disk cache can enable the button before the in-memory controller is warm
    if (not entry or not entry.articles) and current:
        cached = load_news_cache(current)
        if cached and cached.articles:
            entry = cached

    ready = bool(entry and entry.articles)
    loading = bool(
        entry
        and getattr(entry, "status", "") in ("loading", "refreshing")
    )
    # Also treat controller loading without articles as loading
    if ctrl and current and ctrl.is_loading(current):
        loading = True

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
            if ready and not loading:
                dot.configure(text="●", text_color=ACCENT_SUCCESS)
            elif loading:
                dot.configure(text="●", text_color="#f59e0b")
            elif ready:
                dot.configure(text="●", text_color=ACCENT_SUCCESS)
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

    # Prefer live controller state; fall back to disk cache
    if not entry or not entry.articles:
        cached = load_news_cache(symbol)
        if cached and cached.articles:
            entry = cached
            ctrl.seed(cached)

    if not entry or not entry.articles:
        # Kick a fetch and open an empty live window that fills in as results arrive
        start_headline_news_enrichment(dashboard, symbol)
        entry = ctrl.get(symbol) or NewsEnrichmentResult(symbol=symbol, status="loading")
        open_headline_news_window(
            dashboard.root,
            symbol=symbol,
            result=entry,
            controller=ctrl,
        )
        return

    # Ensure a background refresh is running so new headlines can stream in
    if not ctrl.is_loading(symbol):
        start_headline_news_enrichment(dashboard, symbol)
        entry = ctrl.get(symbol) or entry

    open_headline_news_window(
        dashboard.root,
        symbol=symbol,
        result=entry,
        controller=ctrl,
    )


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
