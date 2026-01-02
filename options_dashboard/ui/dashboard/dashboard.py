import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import datetime
import os
import json

from options_dashboard.config import MAX_TICKERS, PRESET_FILE
from options_dashboard.state.ticker_state import TickerState
from options_dashboard.data.schwab_api import fetch_stock_price, fetch_option_chain
from options_dashboard.data.csv_loader import load_csv_index
# from ui.dashboard_chart_logic import generate_selected_chart_impl
from options_dashboard.data.schwab_auth import mark_schwab_reset
from ui import dialogs
from ui.dashboard.layout import build_layout
from ui.dashboard.tabs import rebuild_tabs, create_stock_tab, update_table_for_symbol, on_expiration_change
from ui.dashboard.data_controller import fetch_worker, fetch_all_stocks, load_csv_index_data
from ui.dashboard.refresh import start_auto_refresh, auto_refresh_price, auto_refresh_options
from ui.dashboard.charts_controller import generate_selected_chart, generate_chart_group
from style.custom_theme_controller import register_theme_change_callback
from ui.dashboard.single_stock_panel import build_single_stock_panel
from ui.dashboard.stats_modal import open_stats_modal


class Dashboard(ctk.CTkFrame):
    def __init__(self, root, client):
        super().__init__(root)
        self.root = root
        self.client = client

        # ---- state ----
        self.preset_tickers = self.load_preset_tickers()
        self.ticker_tabs = {}
        self.ticker_data = {}

        # ---- binding controllers ----
        self.build_layout = build_layout.__get__(self)
        self.rebuild_tabs = rebuild_tabs.__get__(self)
        self.create_stock_tab = create_stock_tab.__get__(self)
        self.update_table_for_symbol = update_table_for_symbol.__get__(self)
        self.on_expiration_change = on_expiration_change.__get__(self)

        self.fetch_worker = fetch_worker.__get__(self)
        self.fetch_all_stocks = fetch_all_stocks.__get__(self)
        self.load_csv_index_data = load_csv_index_data.__get__(self)

        self.start_auto_refresh = start_auto_refresh.__get__(self)
        self.auto_refresh_price = auto_refresh_price.__get__(self)
        self.auto_refresh_options = auto_refresh_options.__get__(self)

        self.generate_selected_chart = generate_selected_chart.__get__(self)
        self.generate_chart_group = generate_chart_group.__get__(self)
        #---- end of binding controllers

        # ---- layout ----
        self.pack(fill="both", expand=True)
        self.build_layout()
        build_single_stock_panel(self)
        register_theme_change_callback(self.rebuild)
        self.rebuild_tabs()
        self.start_auto_refresh()

    def rebuild(self):
        self.destroy()
        Dashboard(self.root, self.client)

    def load_preset_tickers(self):
        if os.path.exists(PRESET_FILE):
            try:
                with open(PRESET_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [s.upper() for s in data][:MAX_TICKERS]
            except Exception:
                pass
        return ["SPY"]

    def save_preset_tickers(self):
        try:
            with open(PRESET_FILE, "w") as f:
                json.dump(self.preset_tickers, f, indent=2)
        except Exception as e:
            dialogs.error("Error", f"Failed to save presets:\n{e}")

    def edit_tickers(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Edit Preset Tickers")
        win.geometry("300x300")

        entries = []

        for i in range(MAX_TICKERS):
            var = tk.StringVar(
                value=self.preset_tickers[i] if i < len(self.preset_tickers) else ""
            )
            ctk.CTkEntry(win, textvariable=var).pack(pady=4, padx=20)
            entries.append(var)

        def save():
            self.preset_tickers = [
                v.get().strip().upper()
                for v in entries
                if v.get().strip()
            ][:MAX_TICKERS]

            self.save_preset_tickers()
            self.rebuild_tabs()
            win.destroy()

        ctk.CTkButton(win, text="Save", command=save).pack(pady=10)

    def open_stats(self):
        tab_id = self.notebook.select()
        symbol = self.notebook.tab(tab_id, "text")
        state = self.ticker_data.get(symbol)
        exp = self.ticker_tabs[symbol]["exp_var"].get()

        open_stats_modal(self.root, state, exp)