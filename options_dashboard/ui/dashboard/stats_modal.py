import customtkinter as ctk
import numpy as np
from scipy.stats import norm
from utils.time import time_to_expiration
from config import RISK_FREE_RATE, DIVIDEND_YIELD


def open_stats_modal(root, state, expiration):
    df = state.exp_data_map.get(expiration)
    if df is None or df.empty:
        return

    T = time_to_expiration(expiration)
    S = state.price

    def bs_vega(S, K, T, r, q, sigma):
        if T <= 0 or sigma <= 0:
            return 0
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) * 100

    call_oi = df["OI_Call"].sum()
    put_oi = df["OI_Put"].sum()

    call_gamma = df["Gamma_Call"].sum()
    put_gamma = df["Gamma_Put"].sum()

    call_vega = sum(
        bs_vega(S, row["Strike"], T, RISK_FREE_RATE, DIVIDEND_YIELD, row["IV_Call"])
        for _, row in df.iterrows()
    )

    put_vega = sum(
        bs_vega(S, row["Strike"], T, RISK_FREE_RATE, DIVIDEND_YIELD, row["IV_Put"])
        for _, row in df.iterrows()
    )

    def ratio(a, b): return a / b if b else 0

    rows = [
        ("Put/Call OI", ratio(put_oi, call_oi)),
        ("Put/Call Gamma", ratio(put_gamma, call_gamma)),
        ("Put/Call Vega", ratio(put_vega, call_vega)),
    ]

    win = ctk.CTkToplevel(root)
    win.title("Stats Breakdown")
    win.geometry("420x300")

    for label, value in rows:
        ctk.CTkLabel(win, text=label).pack(pady=4)
        ctk.CTkLabel(win, text=f"{value:.3f}", font=("Segoe UI", 16, "bold")).pack()
