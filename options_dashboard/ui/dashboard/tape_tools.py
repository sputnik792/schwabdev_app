"""
Tape Tools: DEX, volume vs OI, IV smile/skew, expected vs realized move.
"""

from __future__ import annotations

import datetime
import threading

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


from models.tape import (
    SEMI_BOOK_TICKERS,
    build_dex_rows,
    build_gamma_compare_rows,
    build_iv_smile_rows,
    build_volume_oi_rows,
    expected_moves,
    nearest_expiration,
    realized_day_move,
    skew_metrics,
    summarize_tape,
)
from style.theme import ACCENT_PRIMARY, TEXT_MUTED, get_fonts
from ui import dialogs
from ui.charts import compute_bar_width, compute_xticks
from ui.dashboard.save_images import resolve_ticker_state
from ui.windowing import make_independent


def _current_symbol_state(dashboard):
    is_single_view = (
        hasattr(dashboard, "single_view")
        and dashboard.single_view is not None
        and dashboard.single_view.winfo_viewable()
    )
    if is_single_view:
        symbol = getattr(dashboard, "single_view_symbol", None)
        if not symbol:
            return None, None, None
        key, state = resolve_ticker_state(dashboard, symbol)
        ui = dashboard.ticker_tabs.get(f"_single_{symbol.replace(' (CSV)', '')}")
        exp = None
        if ui and ui.get("exp_var"):
            exp = ui["exp_var"].get()
        elif hasattr(dashboard, "single_view_exp_var"):
            exp = dashboard.single_view_exp_var.get()
        return key or symbol, state, exp

    if not hasattr(dashboard, "notebook") or not dashboard.notebook:
        return None, None, None
    tab_id = dashboard.notebook.select()
    if not tab_id:
        return None, None, None
    symbol = dashboard.notebook.tab(tab_id, "text")
    key, state = resolve_ticker_state(dashboard, symbol)
    ui = dashboard.ticker_tabs.get(symbol)
    exp = ui["exp_var"].get() if ui and ui.get("exp_var") else None
    return key or symbol, state, exp


def _plot_dex(ax, dex, spot, fontsize=8):
    if dex is None or dex.empty:
        ax.set_title("Delta Exposure — no OI")
        return
    calls = dex[dex["Type"] == "CALL"]
    puts = dex[dex["Type"] == "PUT"]
    strikes = sorted(dex["Strike"].unique())
    ax.bar(
        calls["Strike"],
        calls["Exposure"] / 1e6,
        width=compute_bar_width(strikes),
        color="#2ECC71",
        edgecolor="black",
        linewidth=0.4,
        label="CALL",
    )
    ax.bar(
        puts["Strike"],
        puts["Exposure"] / 1e6,
        width=compute_bar_width(strikes),
        color="#E74C3C",
        edgecolor="black",
        linewidth=0.4,
        label="PUT",
    )
    ax.axvline(spot, color="#3b82f6", linestyle="--", linewidth=1.4, label=f"Spot {spot:.2f}")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Delta Exposure (DEX, $M)")
    ax.set_ylabel("$ millions")
    ax.set_xlim(min(strikes), max(strikes))
    ax.set_xticks(compute_xticks(strikes))
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(fontsize=fontsize)
    ax.ticklabel_format(style="plain", axis="x")


def _plot_volume_oi(ax, vol_oi, spot, fontsize=7):
    if vol_oi is None or vol_oi.empty:
        ax.set_title("Volume vs OI — no data")
        return
    strikes = sorted(vol_oi["Strike"].unique())
    width = compute_bar_width(strikes)
    calls = vol_oi[vol_oi["Type"] == "CALL"]
    puts = vol_oi[vol_oi["Type"] == "PUT"]
    ax.bar(
        calls["Strike"] - width * 0.2,
        calls["OpenInterest"],
        width=width * 0.4,
        color="#93c5fd",
        label="Call OI",
    )
    ax.bar(
        puts["Strike"] + width * 0.2,
        puts["OpenInterest"],
        width=width * 0.4,
        color="#fecaca",
        label="Put OI",
    )
    ax.plot(calls["Strike"], calls["Volume"], color="#166534", marker="o", linewidth=1.2, label="Call vol")
    ax.plot(puts["Strike"], puts["Volume"], color="#991b1b", marker="o", linewidth=1.2, label="Put vol")
    ax.axvline(spot, color="#3b82f6", linestyle="--", linewidth=1.4, label=f"Spot {spot:.2f}")
    ax.set_title("Volume vs Open Interest")
    ax.set_xlim(min(strikes), max(strikes))
    ax.set_xticks(compute_xticks(strikes))
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(fontsize=fontsize)
    ax.ticklabel_format(style="plain", axis="x")


def _plot_smile(ax, smile, spot, fontsize=8):
    if smile is None or smile.empty:
        ax.set_title("IV Smile — no IV")
        return
    calls = smile[smile["Type"] == "CALL"]
    puts = smile[smile["Type"] == "PUT"]
    ax.plot(calls["Strike"], calls["IV"], color="#16a34a", marker="o", label="Call IV")
    ax.plot(puts["Strike"], puts["IV"], color="#dc2626", marker="o", label="Put IV")
    ax.axvline(spot, color="#3b82f6", linestyle="--", linewidth=1.4, label=f"Spot {spot:.2f}")
    ax.set_title("IV Smile (%)")
    ax.set_ylabel("Implied vol")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(fontsize=fontsize)
    ax.ticklabel_format(style="plain", axis="x")


def _plot_gamma_compare(ax, gcmp, spot, fontsize=8):
    if gcmp is None or gcmp.empty:
        ax.set_title("Gamma compare — no data")
        return
    ax.plot(gcmp["Strike"], gcmp["ChainGamma"], color="#7c3aed", marker="o", linewidth=1, label="Chain gamma")
    ax.plot(gcmp["Strike"], gcmp["BSGamma"], color="#f59e0b", marker="x", linewidth=1, label="BS gamma")
    ax.axvline(spot, color="#3b82f6", linestyle="--", linewidth=1.4, label=f"Spot {spot:.2f}")
    ax.set_title("Chain gamma vs Black-Scholes")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(fontsize=fontsize)
    ax.ticklabel_format(style="plain", axis="x")


def _open_chart_window(root, title, draw_fn) -> None:
    win = ctk.CTkToplevel(root)
    win.title(title)
    win.geometry("980x720")
    make_independent(win)

    fig = Figure(figsize=(9.6, 6.6), dpi=110)
    ax = fig.add_subplot(111)
    draw_fn(ax)
    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
    win.lift()
    win.focus_force()


def _metric_card(parent, title, value, fonts):
    card = ctk.CTkFrame(parent, corner_radius=10)
    ctk.CTkLabel(card, text=title, font=fonts["sm"], text_color=TEXT_MUTED).pack(
        anchor="w", padx=10, pady=(8, 0)
    )
    ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold")).pack(
        anchor="w", padx=10, pady=(0, 8)
    )
    return card


def show_tape_tools_window(dashboard) -> None:
    fonts = get_fonts()
    symbol, state, exp = _current_symbol_state(dashboard)
    if not state or not exp:
        dialogs.warning("No Data", "Fetch a ticker and select an expiration first.")
        return

    df = state.exp_data_map.get(exp)
    if df is None or df.empty:
        dialogs.warning("No Chain", f"No option chain for {symbol} {exp}.")
        return

    spot = state.price
    quote = getattr(state, "quote", None) or {}
    exp_date = exp.split(":")[0] if ":" in exp else exp
    expect = expected_moves(df, spot, exp)
    realized = realized_day_move(quote, spot)
    skew = skew_metrics(df, spot)
    dex = build_dex_rows(df, spot, exp)
    vol_oi = build_volume_oi_rows(df)
    smile = build_iv_smile_rows(df, spot)
    gcmp = build_gamma_compare_rows(df, spot, exp)

    win = ctk.CTkToplevel(dashboard.root)
    win.title(f"Tape Tools — {symbol}")
    win.geometry("1180x860")
    make_independent(win)

    shell = ctk.CTkFrame(win, corner_radius=14)
    shell.pack(fill="both", expand=True, padx=12, pady=12)

    header = ctk.CTkFrame(shell, fg_color="transparent")
    header.pack(fill="x", padx=8, pady=(8, 4))
    fetched = ""
    if getattr(state, "last_updated", None):
        fetched = state.last_updated.strftime("%I:%M %p")
    ctk.CTkLabel(
        header,
        text=f"{symbol}  |  {exp_date}  |  spot ${spot:.2f}  |  fetched {fetched or '—'}",
        font=fonts["lg"],
    ).pack(side="left")
    ctk.CTkButton(
        header,
        text="Semi Book (SOXL / SOXX / NVDA)",
        command=lambda: show_semi_book_window(dashboard),
        width=240,
        height=30,
        font=fonts["sm"],
        fg_color=ACCENT_PRIMARY,
    ).pack(side="right", padx=(8, 0))
    ctk.CTkLabel(
        header,
        text=datetime.datetime.now().strftime("%I:%M %p"),
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    ).pack(side="right")

    metrics = ctk.CTkFrame(shell, fg_color="transparent")
    metrics.pack(fill="x", padx=8, pady=(4, 8))
    cards = [
        ("Day change", f"{realized['change']:+.2f} ({realized['change_pct']:+.1f}%)"),
        ("Day range", f"{realized['low']:.2f} – {realized['high']:.2f}" if realized["high"] else "—"),
        ("Prev close", f"${realized['close']:.2f}" if realized["close"] else "—"),
        ("ATM IV", f"{expect['atm_iv']:.1f}%"),
        ("Exp. move (exp)", f"±{expect['exp_move']:.2f} ({expect['exp_move_pct']:.1f}%)"),
        ("Exp. 1-day", f"±{expect['day_move']:.2f} ({expect['day_move_pct']:.1f}%)"),
        ("Realized range", f"{realized['range']:.2f} ({realized['range_pct']:.1f}%)"),
        ("25d skew (P-C)", f"{skew['skew_25d']:+.1f} vol"),
        ("P/C OI", f"{skew['pc_oi']:.2f}"),
        ("P/C volume", f"{skew['pc_volume']:.2f}"),
    ]
    for i, (title, value) in enumerate(cards):
        card = _metric_card(metrics, title, value, fonts)
        card.grid(row=i // 5, column=i % 5, sticky="nsew", padx=4, pady=4)
        metrics.grid_columnconfigure(i % 5, weight=1)

    fig = Figure(figsize=(11.4, 6.4), dpi=100)
    axes = fig.subplots(2, 2)
    fig.tight_layout(pad=3.0)
    _plot_dex(axes[0, 0], dex, spot)
    _plot_volume_oi(axes[0, 1], vol_oi, spot)
    _plot_smile(axes[1, 0], smile, spot)
    _plot_gamma_compare(axes[1, 1], gcmp, spot)

    canvas_frame = ctk.CTkFrame(shell)
    canvas_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

    open_row = ctk.CTkFrame(shell, fg_color="transparent")
    open_row.pack(fill="x", padx=8, pady=(0, 6))
    ctk.CTkLabel(
        open_row,
        text="Open larger:",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
    ).pack(side="left", padx=(4, 8))

    root = dashboard.root
    popouts = [
        ("DEX", f"{symbol} DEX — {exp_date}", lambda ax, d=dex, s=spot: _plot_dex(ax, d, s, fontsize=10)),
        ("Volume vs OI", f"{symbol} Volume vs OI — {exp_date}", lambda ax, v=vol_oi, s=spot: _plot_volume_oi(ax, v, s, fontsize=10)),
        ("IV Smile", f"{symbol} IV Smile — {exp_date}", lambda ax, sm=smile, s=spot: _plot_smile(ax, sm, s, fontsize=10)),
        ("Gamma compare", f"{symbol} Chain vs BS Gamma — {exp_date}", lambda ax, g=gcmp, s=spot: _plot_gamma_compare(ax, g, s, fontsize=10)),
    ]
    for label, title, drawer in popouts:
        ctk.CTkButton(
            open_row,
            text=label,
            width=130,
            height=30,
            font=fonts["sm"],
            command=lambda t=title, d=drawer: _open_chart_window(root, t, d),
        ).pack(side="left", padx=4)

    ctk.CTkLabel(
        shell,
        text="DEX uses chain delta × OI × 100 × spot. Blue dashed line is live spot. "
             "Refetch the ticker before trusting CPI-day numbers.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        wraplength=1100,
        justify="left",
    ).pack(anchor="w", padx=12, pady=(0, 10))


def _build_semi_book_state(dashboard, symbol: str):
    from data.schwab_api import fetch_stock_quote
    from state.ticker_state import TickerState
    from ui.dashboard.data_controller import (
        fetch_exp_map_with_prob_itm,
        get_strike_count_label,
    )

    strike_label = get_strike_count_label(dashboard, symbol)
    quote = fetch_stock_quote(dashboard.client, symbol)
    price = quote.get("price") or 0.0
    exp_map, _expirations = fetch_exp_map_with_prob_itm(
        dashboard.client, symbol, price, strike_label
    )
    return TickerState(
        symbol=symbol,
        price=price,
        exp_data_map=exp_map,
        last_updated=datetime.datetime.now(),
        strike_count_label=strike_label,
        quote=quote,
    )


def show_semi_book_window(dashboard) -> None:
    """Always-on SOXL / SOXX / NVDA comparison strip."""
    fonts = get_fonts()
    if not getattr(dashboard, "client", None):
        dialogs.error("Not Connected", "Schwab client is not available.")
        return

    _symbol, _state, current_exp = _current_symbol_state(dashboard)
    preferred_date = None
    if current_exp:
        preferred_date = current_exp.split(":")[0] if ":" in current_exp else current_exp

    progress = dialogs.show_fetching_dialog(
        dashboard.root,
        "Semi Book",
        "Fetching SOXL, SOXX, and NVDA...",
    )

    def worker():
        fetched = {}
        errors = {}
        for ticker in SEMI_BOOK_TICKERS:
            try:
                fetched[ticker] = _build_semi_book_state(dashboard, ticker)
            except Exception as exc:
                errors[ticker] = str(exc)

        def finish():
            try:
                if progress.winfo_exists():
                    progress.destroy()
            except Exception:
                pass
            for ticker, state in fetched.items():
                existing = dashboard.ticker_data.get(ticker)
                if existing and getattr(existing, "_from_single_view", False):
                    state._from_single_view = True
                dashboard.ticker_data[ticker] = state
            if len(errors) == len(SEMI_BOOK_TICKERS):
                dialogs.error(
                    "Semi Book Failed",
                    "Could not fetch SOXL, SOXX, or NVDA.\n"
                    + "\n".join(f"{t}: {msg}" for t, msg in errors.items()),
                )
                return
            _render_semi_book_window(dashboard, fonts, preferred_date, errors)

        dashboard.root.after(0, finish)

    threading.Thread(target=worker, daemon=True).start()


def _render_semi_book_window(dashboard, fonts, preferred_date, errors) -> None:
    win = ctk.CTkToplevel(dashboard.root)
    win.title("Semi Book — SOXL / SOXX / NVDA")
    win.geometry("1180x720")
    make_independent(win)

    shell = ctk.CTkFrame(win, corner_radius=14)
    shell.pack(fill="both", expand=True, padx=12, pady=12)

    header = ctk.CTkFrame(shell, fg_color="transparent")
    header.pack(fill="x", padx=8, pady=(8, 6))
    ctk.CTkLabel(
        header,
        text="Semi Book  ·  dealer tape for the semiconductor complex",
        font=fonts["lg"],
    ).pack(side="left")
    ctk.CTkButton(
        header,
        text="Refresh",
        command=lambda: (win.destroy(), show_semi_book_window(dashboard)),
        width=90,
        height=30,
        font=fonts["sm"],
    ).pack(side="right")

    if errors:
        ctk.CTkLabel(
            shell,
            text="Partial fetch: " + ", ".join(f"{t} ({errors[t]})" for t in errors),
            font=fonts["sm"],
            text_color=TEXT_MUTED,
            wraplength=1100,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 6))

    cards = ctk.CTkFrame(shell, fg_color="transparent")
    cards.pack(fill="x", padx=8, pady=(0, 8))
    summaries = []
    for i, ticker in enumerate(SEMI_BOOK_TICKERS):
        state = dashboard.ticker_data.get(ticker)
        exp = nearest_expiration(state, preferred_date) if state else None
        summary = summarize_tape(state, exp or "") if state else None
        summaries.append((ticker, summary, exp))

        col = ctk.CTkFrame(cards, corner_radius=12)
        col.grid(row=0, column=i, sticky="nsew", padx=6)
        cards.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(
            col,
            text=ticker,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=ACCENT_PRIMARY,
        ).pack(anchor="w", padx=12, pady=(12, 2))

        if not summary or summary.get("error"):
            ctk.CTkLabel(
                col,
                text=errors.get(ticker) or summary.get("error") if summary else "No data",
                font=fonts["sm"],
                text_color=TEXT_MUTED,
                wraplength=320,
                justify="left",
            ).pack(anchor="w", padx=12, pady=(4, 12))
            continue

        realized = summary["realized"]
        expect = summary["expect"]
        skew = summary["skew"]
        exp_label = (summary["expiration"] or "").split(":")[0]
        lines = [
            f"Spot  ${summary['spot']:.2f}",
            f"Day  {realized['change']:+.2f}  ({realized['change_pct']:+.1f}%)",
            f"Range  {realized['low']:.2f} – {realized['high']:.2f}" if realized["high"] else "Range  —",
            f"Expiry  {exp_label or '—'}",
            f"ATM IV  {expect['atm_iv']:.1f}%",
            f"1-day exp  ±{expect['day_move_pct']:.1f}%",
            f"Realized  {realized['range_pct']:.1f}% of prev close",
            f"25d skew  {skew['skew_25d']:+.1f}",
            f"P/C vol  {skew['pc_volume']:.2f}    P/C OI  {skew['pc_oi']:.2f}",
            f"Net DEX  ${summary['net_dex'] / 1e6:,.1f}M",
        ]
        for line in lines:
            ctk.CTkLabel(col, text=line, font=fonts["sm"], anchor="w").pack(
                anchor="w", padx=12, pady=1
            )
        dex_df = summary.get("dex")
        spot_px = summary.get("spot")
        ctk.CTkButton(
            col,
            text="Open DEX",
            width=110,
            height=28,
            font=fonts["sm"],
            command=lambda t=ticker, d=dex_df, s=spot_px: _open_chart_window(
                dashboard.root,
                f"{t} DEX",
                lambda ax, dd=d, ss=s: _plot_dex(ax, dd, ss, fontsize=10),
            ),
        ).pack(anchor="w", padx=12, pady=(8, 12))

    fig = Figure(figsize=(11.4, 3.6), dpi=100)
    axes = fig.subplots(1, 3)
    fig.tight_layout(pad=2.4)
    for ax, (ticker, summary, _exp) in zip(axes, summaries):
        if not summary or summary.get("error") or summary.get("dex") is None or summary["dex"].empty:
            ax.set_title(f"{ticker} DEX — no data")
            continue
        dex = summary["dex"]
        spot = summary["spot"]
        calls = dex[dex["Type"] == "CALL"]
        puts = dex[dex["Type"] == "PUT"]
        strikes = sorted(dex["Strike"].unique())
        ax.bar(
            calls["Strike"],
            calls["Exposure"] / 1e6,
            width=compute_bar_width(strikes),
            color="#2ECC71",
            edgecolor="black",
            linewidth=0.3,
            label="CALL",
        )
        ax.bar(
            puts["Strike"],
            puts["Exposure"] / 1e6,
            width=compute_bar_width(strikes),
            color="#E74C3C",
            edgecolor="black",
            linewidth=0.3,
            label="PUT",
        )
        ax.axvline(spot, color="#3b82f6", linestyle="--", linewidth=1.2)
        ax.axhline(0, color="black", linewidth=0.7)
        ax.set_title(f"{ticker} DEX ($M)")
        ax.set_xlim(min(strikes), max(strikes))
        ax.set_xticks(compute_xticks(strikes))
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.ticklabel_format(style="plain", axis="x")

    canvas_frame = ctk.CTkFrame(shell)
    canvas_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

    ctk.CTkLabel(
        shell,
        text="SOXL is the 3x side bet. SOXX / NVDA are closer to where dealer hedges actually live. "
             "Compare day % and 1-day expected move first, then whether DEX is sitting on the blue spot line.",
        font=fonts["sm"],
        text_color=TEXT_MUTED,
        wraplength=1100,
        justify="left",
    ).pack(anchor="w", padx=12, pady=(0, 10))
