import customtkinter as ctk
import tkinter as tk
from ui import dialogs
from models.greeks import gamma, vanna, volga, charm, vega
from models.exposure import gamma_exposure, vanna_exposure, volga_exposure, charm_exposure

from ui.charts import build_exposure_dataframe, generate_altair_chart, embed_matplotlib_chart
from utils.time import time_to_expiration
from models.dealer import find_zero_gamma
from config import RISK_FREE_RATE, DIVIDEND_YIELD
from ui.charts import open_altair_chart
from ui.controls import spot_slider

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

    T = time_to_expiration(exp)

    CONTRACT_MULT = 100
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

            # ---------- GAMMA ----------
            if self.model_var.get() == "Gamma":
                g = gamma(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * CONTRACT_MULT * (spot ** 2) * 0.01
                exp_val = sign * g * scale   # ONLY gamma uses sign flip

            # ---------- VANNA ----------
            elif self.model_var.get() == "Vanna":
                v = vanna(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * CONTRACT_MULT * spot * iv
                exp_val = sign * abs(v) * scale

            # ---------- VOLGA ----------
            elif self.model_var.get() == "Volga":
                vg = volga(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                ve = vega(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * ve
                exp_val = sign * abs(vg) * scale

            # ---------- CHARM ----------
            else:  # Charm
                c = charm(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * CONTRACT_MULT * spot
                exp_val = sign * abs(c) * scale

            rows.append({
                "Strike": K,
                "Type": opt,
                "Exposure": exp_val
            })

    if not rows:
        dialogs.warning(
            "No Exposure Data",
            "No valid options found for this expiration.\n"
            "IV or Open Interest may be missing."
        )
        return

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
    for w in self.sidebar.winfo_children():
        if isinstance(w, (tk.Scale, ctk.CTkSlider)):
            w.destroy()

    spot_slider(self.sidebar, spot, self.generate_selected_chart)


def generate_chart_group(self):
    for symbol, ui in self.ticker_tabs.items():
        if symbol in self.ticker_data:
            self.notebook.select(ui["tab"])
            generate_selected_chart(self)
