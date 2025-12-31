import os
import json
import threading
import datetime
import tkinter as tk
from tkinter import ttk

from config import MAX_TICKERS, PRESET_FILE
from state.ticker_state import TickerState
from ui import dialogs
from data.schwab_api import fetch_stock_price, fetch_option_chain
from data.csv_loader import load_csv_index


class Dashboard(tk.Frame):
    def __init__(self, root, client):
        super().__init__(root)
        self.root = root
        self.client = client

        # ---- state ----
        self.preset_tickers = self.load_preset_tickers()
        self.ticker_tabs = {}     # symbol -> UI refs
        self.ticker_data = {}     # symbol -> TickerState

        # ---- layout ----
        self.pack(fill=tk.BOTH, expand=True)
        self.build_layout()
        self.add_csv_controls()
        self.add_chart_controls()
        self.rebuild_tabs()
        self.start_auto_refresh()

    # =========================
    # Preset ticker persistence
    # =========================

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

    # =========================
    # Layout
    # =========================

    def build_layout(self):
        self.top_bar = tk.Frame(self)
        self.top_bar.pack(fill=tk.X, pady=4)

        ttk.Button(
            self.top_bar,
            text="Fetch All",
            command=self.fetch_all_stocks
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.top_bar,
            text="Edit Preset Tickers",
            command=self.edit_tickers
        ).pack(side=tk.LEFT, padx=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

    # =========================
    # Tabs
    # =========================

    def rebuild_tabs(self):
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        self.ticker_tabs.clear()

        for symbol in self.preset_tickers:
            self.create_stock_tab(symbol)

    def create_stock_tab(self, symbol):
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=symbol)

        price_var = tk.StringVar(value="—")
        exp_var = tk.StringVar()

        top = tk.Frame(tab)
        top.pack(pady=4)

        tk.Label(top, text=f"{symbol} Price:").pack(side=tk.LEFT)
        tk.Label(
            top,
            textvariable=price_var,
            fg="blue",
            font=("Arial", 11, "bold")
        ).pack(side=tk.LEFT, padx=6)

        tk.Label(top, text="Expiration:").pack(side=tk.LEFT)
        exp_dropdown = ttk.Combobox(
            top,
            textvariable=exp_var,
            state="readonly",
            width=24
        )
        exp_dropdown.pack(side=tk.LEFT, padx=5)
        exp_dropdown.bind(
            "<<ComboboxSelected>>",
            lambda e, s=symbol: self.on_expiration_change(e, s)
        )

        self.ticker_tabs[symbol] = {
            "tab": tab,
            "price_var": price_var,
            "exp_var": exp_var,
            "exp_dropdown": exp_dropdown,
        }
        self.attach_table_to_tab(symbol)
        
    # =========================
    # Preset editor
    # =========================

    def edit_tickers(self):
        win = tk.Toplevel(self.root)
        win.title("Edit Preset Tickers")
        win.geometry("300x250")

        entries = []

        for i in range(MAX_TICKERS):
            var = tk.StringVar(
                value=self.preset_tickers[i] if i < len(self.preset_tickers) else ""
            )
            e = ttk.Entry(win, textvariable=var)
            e.pack(pady=3)
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

        ttk.Button(win, text="Save", command=save).pack(pady=8)

    # =========================
    # Option Table
    # =========================

    def create_option_table(self, parent):
        cols = [
            "Bid_Call", "Ask_Call", "Delta_Call", "Theta_Call",
            "Gamma_Call", "IV_Call", "OI_Call",
            "Strike",
            "Bid_Put", "Ask_Put", "Delta_Put", "Theta_Put",
            "Gamma_Put", "IV_Put", "OI_Put"
        ]

        headers = [
            "Call Bid", "Call Ask", "Δ(Call)", "Θ(Call)", "Γ(Call)", "IV(Call)", "OI(Call)",
            "Strike",
            "Put Bid", "Put Ask", "Δ(Put)", "Θ(Put)", "Γ(Put)", "IV(Put)", "OI(Put)"
        ]

        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h in zip(cols, headers):
            tree.heading(c, text=h)
            tree.column(c, width=95, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)

        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(fill=tk.BOTH, expand=True)

        return tree, cols

    def attach_table_to_tab(self, symbol):
        ui = self.ticker_tabs[symbol]
        tree, cols = self.create_option_table(ui["tab"])
        ui["tree"] = tree
        ui["cols"] = cols

    def update_table_for_symbol(self, symbol, expiration):
        ui = self.ticker_tabs.get(symbol)
        if not ui or symbol not in self.ticker_data:
            return

        tree = ui["tree"]
        cols = ui["cols"]

        tree.delete(*tree.get_children())

        df = self.ticker_data[symbol].exp_data_map.get(expiration)
        if df is None or df.empty:
            return

        for _, row in df.iterrows():
            tree.insert(
                "",
                tk.END,
                values=[row.get(c, "") for c in cols]
            )

    # =========================
    # Schwab Fetching
    # =========================

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

            def update_ui():
                self.ticker_data[symbol] = state
                ui = self.ticker_tabs.get(symbol)
                if not ui:
                    return

                ui["price_var"].set(f"${price:.2f}" if price else "—")

                if expirations:
                    ui["exp_dropdown"]["values"] = expirations
                    ui["exp_var"].set(expirations[0])
                    self.update_table_for_symbol(symbol, expirations[0])

            self.root.after(0, update_ui)

        except RuntimeError as e:
            if str(e) == "AUTH_REQUIRED":
                self.root.after(
                    0,
                    lambda: dialogs.error(
                        "Authentication Required",
                        "Schwab authentication expired.\nPlease reconnect."
                    )
                )
        except Exception as e:
            self.root.after(
                0,
                lambda: dialogs.error("Error", f"{symbol}: {e}")
            )

    def fetch_all_stocks(self):
        for symbol in self.preset_tickers:
            threading.Thread(
                target=self.fetch_worker,
                args=(symbol,),
                daemon=True
            ).start()

    # =========================
    # Expiration change handler
    # =========================

    def on_expiration_change(self, event, symbol):
        ui = self.ticker_tabs.get(symbol)
        if not ui:
            return

        exp = ui["exp_var"].get()
        self.update_table_for_symbol(symbol, exp)

    # =========================
    # CSV Index Controls
    # =========================

    def add_csv_controls(self):
        bar = tk.Frame(self)
        bar.pack(fill=tk.X, pady=6)

        tk.Label(bar, text="CS Index:").pack(side=tk.LEFT, padx=4)

        self.csv_symbol_var = tk.StringVar(value="SPX")
        ttk.Combobox(
            bar,
            textvariable=self.csv_symbol_var,
            values=["SPX", "NDX", "VIX"],
            state="readonly",
            width=6
        ).pack(side=tk.LEFT, padx=4)

        self.csv_mode_var = tk.StringVar(value="Default File")
        ttk.Combobox(
            bar,
            textvariable=self.csv_mode_var,
            values=["Default File", "Choose CSV File"],
            state="readonly",
            width=14
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            bar,
            text="Fetch CS Index",
            command=self.load_csv_index_data
        ).pack(side=tk.LEFT, padx=6)

    def load_csv_index_data(self):
        symbol = self.csv_symbol_var.get()

        if self.csv_mode_var.get() == "Default File":
            filename = f"{symbol.lower()}_quotedata.csv"
        else:
            from tkinter import filedialog
            filename = filedialog.askopenfilename(
                title=f"Select {symbol} CSV File",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
            )
            if not filename:
                return

        try:
            exp_map, expirations, spot, display_symbol = load_csv_index(
                symbol,
                filename
            )

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

            dialogs.info(
                "CSV Loaded",
                f"{display_symbol} options loaded successfully."
            )

        except Exception as e:
            dialogs.error("CSV Error", str(e))

    # =========================
    # Chart Controls
    # =========================

    def add_chart_controls(self):
        side = tk.Frame(self)
        side.pack(fill=tk.Y, side=tk.LEFT, padx=6)

        self.chart_output_var = tk.StringVar(value="Desktop")
        ttk.Combobox(
            side,
            textvariable=self.chart_output_var,
            values=["Browser", "Desktop"],
            state="readonly",
            width=10
        ).pack(pady=4)

        self.model_var = tk.StringVar(value="Gamma")
        model_btn = tk.Menubutton(side, text="Exposure Model", relief=tk.RAISED)
        model_menu = tk.Menu(model_btn, tearoff=0)
        model_btn.config(menu=model_menu)

        for m in ["Gamma", "Vanna", "Volga", "Charm"]:
            model_menu.add_radiobutton(
                label=m,
                variable=self.model_var,
                value=m
            )

        model_btn.pack(fill=tk.X, pady=4)

        ttk.Button(
            side,
            text="Generate Chart",
            command=self.generate_selected_chart
        ).pack(fill=tk.X, pady=4)

        ttk.Button(
            side,
            text="Generate Chart Group",
            command=self.generate_chart_group
        ).pack(fill=tk.X, pady=4)

        self.side_panel = side

    # =========================
    # Chart generation
    # =========================

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
            win = tk.Toplevel(self.root)
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
        for w in self.side_panel.winfo_children():
            if isinstance(w, tk.Scale):
                w.destroy()

        spot_slider(self.side_panel, spot, self.generate_selected_chart)

    def generate_chart_group(self):
        for symbol, state in self.ticker_data.items():
            ui = self.ticker_tabs.get(symbol)
            if not ui:
                continue
            exp = ui["exp_var"].get()
            if exp:
                self.notebook.select(ui["tab"])
                self.generate_selected_chart()

    # =========================
    # Auto Refresh
    # =========================

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
                        if not state:
                            return
                        diff = price - state.price
                        state.price = price

                        ui = self.ticker_tabs.get(sym)
                        if ui:
                            ui["price_var"].set(f"${price:.2f}")

                    self.root.after(0, update)

                except RuntimeError as e:
                    if str(e) == "AUTH_REQUIRED":
                        self.root.after(
                            0,
                            lambda: dialogs.error(
                                "Authentication Required",
                                "Schwab authentication expired.\nPlease reconnect."
                            )
                        )

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

                        prev_exp = ui["exp_var"].get()
                        state.exp_data_map = exp_map

                        ui["exp_dropdown"]["values"] = expirations
                        if prev_exp in expirations:
                            ui["exp_var"].set(prev_exp)
                        else:
                            ui["exp_var"].set(expirations[0])

                        self.update_table_for_symbol(sym, ui["exp_var"].get())

                    self.root.after(0, update)

                except RuntimeError as e:
                    if str(e) == "AUTH_REQUIRED":
                        self.root.after(
                            0,
                            lambda: dialogs.error(
                                "Authentication Required",
                                "Schwab authentication expired.\nPlease reconnect."
                            )
                        )

            threading.Thread(target=worker, daemon=True).start()

        self.root.after(120000, self.auto_refresh_options)
