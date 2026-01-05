import customtkinter as ctk
import datetime
import numpy as np
from scipy.stats import norm
from utils.time import time_to_expiration
from config import RISK_FREE_RATE, DIVIDEND_YIELD


def open_stats_modal(root, state, expiration, symbol=None):
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
    win.geometry("420x400")
    
    # Ensure window stays in front
    win.lift()
    win.focus()
    win.attributes("-topmost", True)
    win.after(100, lambda: win.attributes("-topmost", False))

    # Title section with ticker symbol
    title_frame = ctk.CTkFrame(win, fg_color="transparent")
    title_frame.pack(fill="x", padx=20, pady=(20, 10))
    
    if symbol:
        ctk.CTkLabel(
            title_frame,
            text=symbol,
            font=("Segoe UI", 24, "bold")
        ).pack()
    
    # Expiration date and time generated
    info_frame = ctk.CTkFrame(win, fg_color="transparent")
    info_frame.pack(fill="x", padx=20, pady=(0, 20))
    
    exp_date = expiration.split(":")[0] if ":" in expiration else expiration
    current_datetime = datetime.datetime.now()
    current_date_time_str = current_datetime.strftime('%Y-%m-%d %I:%M:%S %p')
    
    ctk.CTkLabel(
        info_frame,
        text=f"Expiration date: {exp_date}",
        font=("Segoe UI", 12)
    ).pack(anchor="w", pady=2)
    
    ctk.CTkLabel(
        info_frame,
        text=f"Time generated: {current_date_time_str}",
        font=("Segoe UI", 12)
    ).pack(anchor="w", pady=2)
    
    # Separator
    ctk.CTkFrame(win, height=1).pack(fill="x", padx=20, pady=10)

    # Stats rows
    for label, value in rows:
        ctk.CTkLabel(win, text=label).pack(pady=4)
        ctk.CTkLabel(win, text=f"{value:.3f}", font=("Segoe UI", 16, "bold")).pack()
