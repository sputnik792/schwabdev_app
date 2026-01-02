import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import datetime
import os
import json

from config import MAX_TICKERS, PRESET_FILE
from state.ticker_state import TickerState
from data.schwab_api import fetch_stock_price, fetch_option_chain
from data.csv_loader import load_csv_index
# from ui.dashboard_chart_logic import generate_selected_chart_impl
from data.schwab_auth import mark_schwab_reset
from ui import dialogs


class Dashboard(ctk.CTkFrame):
    def __init__(self, root, client):
        super().__init__(root)
        self.root = root
        self.client = client

        # --------------------
        # State
        # --------------------
        self.preset_tickers = self.load_preset_tickers()
        self.ticker_tabs = {}
        self.ticker_data = {}

        # --------------------
        # Layout
        # --------------------
        self.pack(fill="both", expand=True)

        self.build_layout()
        self.rebuild_tabs()
        self.start_auto_refresh()

    # =====================
    # Layout
    # =====================

    def build_layout(self):
        # ---------- Top Bar ----------
        self.top_bar = ctk.CTkFrame(self, height=48)
        self.top_bar.pack(side="top", fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(
            self.top_bar,
            text="Fetch All",
            width=120,
            command=self.fetch_all_stocks
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.top_bar,
            text="Edit Preset Tickers",
            width=180,
            command=self.edit_tickers
        ).pack(side="left", padx=5)

        # ---------- Main Area ----------
        self.main = ctk.CTkFrame(self)
        self.main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # ---------- Sidebar ----------
        self.sidebar = ctk.CTkFrame(self.main, width=220)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10), pady=5)
        self.sidebar.pack_propagate(False)

        self.build_sidebar()

        # ---------- Content ----------
        self.content = ctk.CTkFrame(self.main)
        self.content.pack(side="left", fill="both", expand=True, pady=5)

        self.build_tabs()

    def build_sidebar(self):
        ctk.CTkLabel(
            self.sidebar,
            text="Controls",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(10, 15))

        # Chart output
        self.chart_output_var = tk.StringVar(value="Desktop")
        ctk.CTkLabel(self.sidebar, text="Chart Output").pack(pady=(0, 5))
        ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.chart_output_var,
            values=["Browser", "Desktop"],
            width=160
        ).pack(pady=(0, 15))

        # Exposure model
        self.model_var = tk.StringVar(value="Gamma")
        ctk.CTkLabel(self.sidebar, text="Exposure Model").pack(pady=(0, 5))
        ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Gamma", "Vanna", "Volga", "Charm"],
            variable=self.model_var
        ).pack(pady=(0, 15))

        ctk.CTkButton(
            self.sidebar,
            text="Generate Chart",
            command=self.generate_selected_chart
        ).pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            self.sidebar,
            text="Generate Chart Group",
            command=self.generate_chart_group
        ).pack(fill="x", padx=10, pady=(0, 15))

        # CSV controls
        ctk.CTkLabel(
            self.sidebar,
            text="CSV Index",
            font=ctk.CTkFont(weight="bold")
        ).pack(pady=(10, 5))

        self.csv_symbol_var = tk.StringVar(value="SPX")
        ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.csv_symbol_var,
            values=["SPX", "NDX", "VIX"]
        ).pack(pady=5)

        self.csv_mode_var = tk.StringVar(value="Default File")
        ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.csv_mode_var,
            values=["Default File", "Choose CSV File"]
        ).pack(pady=5)

        ctk.CTkButton(
            self.sidebar,
            text="Load CSV Index",
            command=self.load_csv_index_data
        ).pack(fill="x", padx=10, pady=10)

    def build_tabs(self):
        style = ttk.Style()
        style.theme_use("default")

        self.notebook = ttk.Notebook(self.content)
        self.notebook.pack(fill="both", expand=True)

    # =====================
    # Preset Tickers
    # =====================

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

    # =====================
    # Tabs & Tables
    # =====================

    def rebuild_tabs(self):
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        self.ticker_tabs.clear()

        for symbol in self.preset_tickers:
            self.create_stock_tab(symbol)

    def create_stock_tab(self, symbol):
        tab = ctk.CTkFrame(self.notebook)
        self.notebook.add(tab, text=symbol)

        price_var = tk.StringVar(value="—")
        exp_var = tk.StringVar()

        header = ctk.CTkFrame(tab)
        header.pack(fill="x", pady=5, padx=5)

        ctk.CTkLabel(header, text=f"{symbol} Price:").pack(side="left")
        ctk.CTkLabel(
            header,
            textvariable=price_var,
            font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=10)

        ctk.CTkLabel(header, text="Expiration:").pack(side="left")
        exp_dropdown = ttk.Combobox(
            header,
            textvariable=exp_var,
            state="readonly",
            width=25
        )
        exp_dropdown.pack(side="left", padx=5)
        exp_dropdown.bind(
            "<<ComboboxSelected>>",
            lambda e, s=symbol: self.on_expiration_change(e, s)
        )

        # Table
        frame = ctk.CTkFrame(tab)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        cols = [
            "Bid_Call", "Ask_Call", "Delta_Call", "Theta_Call",
            "Gamma_Call", "IV_Call", "OI_Call",
            "Strike",
            "Bid_Put", "Ask_Put", "Delta_Put", "Theta_Put",
            "Gamma_Put", "IV_Put", "OI_Put"
        ]

        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c.replace("_", " "))
            tree.column(c, width=95, anchor="center")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)

        vsb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        self.ticker_tabs[symbol] = {
            "tab": tab,
            "price_var": price_var,
            "exp_var": exp_var,
            "exp_dropdown": exp_dropdown,
            "tree": tree,
            "cols": cols
        }

    # =====================
    # Data + Updates
    # =====================

    def update_table_for_symbol(self, symbol, expiration):
        ui = self.ticker_tabs.get(symbol)
        if not ui:
            return

        tree = ui["tree"]
        cols = ui["cols"]
        tree.delete(*tree.get_children())

        df = self.ticker_data.get(symbol, {}).exp_data_map.get(expiration)
        if df is None:
            return

        for _, row in df.iterrows():
            tree.insert("", tk.END, values=[row.get(c, "") for c in cols])

    def on_expiration_change(self, event, symbol):
        ui = self.ticker_tabs.get(symbol)
        if not ui:
            return
        self.update_table_for_symbol(symbol, ui["exp_var"].get())

    # =====================
    # Fetching
    # =====================

    def fetch_worker(self, symbol):
        try:
            price = fetch_stock_price(self.client, symbol)
            exp_map, expirations = fetch_option_chain(self.client, symbol)

            state = TickerState(
                symbol=symbol,
                price=price,
                exp_data_map=exp_map,
                last_updated=datetime.datetime.now()
            )

            def update():
                self.ticker_data[symbol] = state
                ui = self.ticker_tabs.get(symbol)
                if not ui:
                    return

                ui["price_var"].set(f"${price:.2f}")

                if expirations:
                    ui["exp_dropdown"]["values"] = expirations
                    ui["exp_var"].set(expirations[0])
                    self.update_table_for_symbol(symbol, expirations[0])

            self.root.after(0, update)

        except Exception as e:
            self.root.after(0, lambda: dialogs.error("Error", f"{symbol}: {e}"))

    def fetch_all_stocks(self):
        for symbol in self.preset_tickers:
            threading.Thread(
                target=self.fetch_worker,
                args=(symbol,),
                daemon=True
            ).start()

    # =====================
    # CSV
    # =====================

    def load_csv_index_data(self):
        symbol = self.csv_symbol_var.get()

        if self.csv_mode_var.get() == "Default File":
            filename = f"{symbol.lower()}_quotedata.csv"
        else:
            from tkinter import filedialog
            filename = filedialog.askopenfilename(
                title=f"Select {symbol} CSV File",
                filetypes=[("CSV Files", "*.csv")]
            )
            if not filename:
                return

        try:
            exp_map, expirations, spot, display_symbol = load_csv_index(symbol, filename)

            state = TickerState(
                symbol=display_symbol,
                price=spot,
                exp_data_map=exp_map,
                last_updated=datetime.datetime.now(),
                is_csv=True
            )

            self.ticker_data[display_symbol] = state

            if display_symbol not in self.ticker_tabs:
                self.preset_tickers.append(display_symbol)
                self.create_stock_tab(display_symbol)

            ui = self.ticker_tabs[display_symbol]
            ui["price_var"].set(f"${spot:.2f}")

            ui["exp_dropdown"]["values"] = expirations
            if expirations:
                ui["exp_var"].set(expirations[0])
                self.update_table_for_symbol(display_symbol, expirations[0])

        except Exception as e:
            dialogs.error("CSV Error", str(e))

    # =====================
    # Charts (logic unchanged)
    # =====================

    def generate_selected_chart(self, spot_override=None):
        tab_id = self.notebook.select()
        if not tab_id:
            return

        symbol = self.notebook.tab(tab_id, "text")
        if symbol not in self.ticker_data:
            dialogs.warning("No Data", "Please fetch data first.")
            return

        state = self.ticker_data[symbol]
        ui = self.ticker_tabs[symbol]
        exp = ui["exp_var"].get()
        if not exp:
            return

        spot = spot_override if spot_override else state.price

        from models.greeks import gamma, vanna, volga, charm
        from models.exposure import (
            gamma_exposure,
            vanna_exposure,
            volga_exposure,
            charm_exposure
        )
        from ui.charts import (
            build_exposure_dataframe,
            generate_altair_chart,
            embed_matplotlib_chart
        )
        from utils.time import time_to_expiration
        from models.dealer import find_zero_gamma
        from config import RISK_FREE_RATE, DIVIDEND_YIELD

        T = time_to_expiration(exp)

        rows = []
        for _, row in state.exp_data_map[exp].iterrows():
            K = float(row["Strike"])
            if K <= 0:
                continue

            for opt in ("CALL", "PUT"):
                iv = float(row.get(f"IV_{opt}", 0) or 0)
                oi = float(row.get(f"OI_{opt}", 0) or 0)
                if iv <= 0 or oi <= 0:
                    continue

                sign = 1 if opt == "CALL" else -1

                if self.model_var.get() == "Gamma":
                    g = gamma(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                    exp_val = gamma_exposure(g, spot, oi)

                elif self.model_var.get() == "Vanna":
                    v = vanna(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                    exp_val = vanna_exposure(v, spot, iv, oi)

                elif self.model_var.get() == "Volga":
                    vg = volga(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                    ve = gamma(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                    exp_val = volga_exposure(vg, ve, oi)

                else:  # Charm
                    c = charm(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                    exp_val = charm_exposure(c, spot, oi)

                rows.append({
                    "Strike": K,
                    "Type": opt,
                    "Exposure": sign * exp_val
                })

        df_plot = build_exposure_dataframe(rows)
        total = df_plot["Exposure"].sum() / 1e9

        zero_gamma = find_zero_gamma(
            state.exp_data_map[exp],
            spot * 0.9,
            spot * 1.1,
            120,
            T,
            RISK_FREE_RATE,
            DIVIDEND_YIELD
        )

        if self.chart_output_var.get() == "Browser":
            chart = generate_altair_chart(
                df_plot,
                symbol,
                exp.split(":")[0],
                self.model_var.get(),
                spot,
                total,
                zero_gamma
            )
            from ui.charts import open_altair_chart
            open_altair_chart(chart, symbol, exp)
        else:
            win = ctk.CTkToplevel(self.root)
            win.geometry("950x700")
            embed_matplotlib_chart(
                win,
                df_plot,
                symbol,
                exp.split(":")[0],
                self.model_var.get(),
                total,
                zero_gamma
            )

        # Spot slider
        from ui.controls import spot_slider
        for w in self.sidebar.winfo_children():
            if isinstance(w, (tk.Scale, ctk.CTkSlider)):
                w.destroy()

        spot_slider(self.sidebar, spot, self.generate_selected_chart)


    def generate_chart_group(self):
        for symbol, ui in self.ticker_tabs.items():
            if symbol in self.ticker_data:
                self.notebook.select(ui["tab"])
                self.generate_selected_chart()

    # =====================
    # Auto Refresh
    # =====================

    def start_auto_refresh(self):
        self.auto_refresh_price()
        self.auto_refresh_options()

    def auto_refresh_price(self):
        for symbol, state in list(self.ticker_data.items()):
            if state.is_csv:
                continue

            def worker(sym=symbol):
                try:
                    price = fetch_stock_price(self.client, sym)
                    if price <= 0:
                        return

                    def update():
                        state = self.ticker_data.get(sym)
                        ui = self.ticker_tabs.get(sym)
                        if state and ui:
                            state.price = price
                            ui["price_var"].set(f"${price:.2f}")

                    self.root.after(0, update)

                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        self.root.after(10000, self.auto_refresh_price)

    def auto_refresh_options(self):
        for symbol, state in list(self.ticker_data.items()):
            if state.is_csv:
                continue

            def worker(sym=symbol):
                try:
                    exp_map, expirations = fetch_option_chain(self.client, sym)
                    if not expirations:
                        return

                    def update():
                        state = self.ticker_data.get(sym)
                        ui = self.ticker_tabs.get(sym)
                        if not state or not ui:
                            return

                        prev = ui["exp_var"].get()
                        state.exp_data_map = exp_map
                        ui["exp_dropdown"]["values"] = expirations
                        ui["exp_var"].set(prev if prev in expirations else expirations[0])
                        self.update_table_for_symbol(sym, ui["exp_var"].get())

                    self.root.after(0, update)

                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        self.root.after(120000, self.auto_refresh_options)
