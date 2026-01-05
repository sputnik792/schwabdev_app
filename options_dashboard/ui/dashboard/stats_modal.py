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
    
    call_delta = df["Delta_Call"].sum()
    put_delta = df["Delta_Put"].sum()
    
    call_theta = df["Theta_Call"].sum()
    put_theta = df["Theta_Put"].sum()
    
    # Calculate IV sums (handle percentage conversion if needed)
    call_iv_sum = 0
    put_iv_sum = 0
    for _, row in df.iterrows():
        iv_call = row.get("IV_Call", 0) or 0
        iv_put = row.get("IV_Put", 0) or 0
        # Convert from percentage if needed
        if iv_call > 1:
            iv_call = iv_call / 100.0
        if iv_put > 1:
            iv_put = iv_put / 100.0
        call_iv_sum += iv_call
        put_iv_sum += iv_put

    call_vega = sum(
        bs_vega(S, row["Strike"], T, RISK_FREE_RATE, DIVIDEND_YIELD, row["IV_Call"])
        for _, row in df.iterrows()
    )

    put_vega = sum(
        bs_vega(S, row["Strike"], T, RISK_FREE_RATE, DIVIDEND_YIELD, row["IV_Put"])
        for _, row in df.iterrows()
    )
    
    # Weighted calculations (OI-weighted)
    weighted_call_gamma = sum(
        (row.get("Gamma_Call", 0) or 0) * (row.get("OI_Call", 0) or 0) 
        for _, row in df.iterrows()
    )
    weighted_put_gamma = sum(
        (row.get("Gamma_Put", 0) or 0) * (row.get("OI_Put", 0) or 0) 
        for _, row in df.iterrows()
    )
    
    weighted_call_vega = sum(
        bs_vega(S, row.get("Strike", 0), T, RISK_FREE_RATE, DIVIDEND_YIELD, row.get("IV_Call", 0) or 0) * (row.get("OI_Call", 0) or 0)
        for _, row in df.iterrows()
    )
    weighted_put_vega = sum(
        bs_vega(S, row.get("Strike", 0), T, RISK_FREE_RATE, DIVIDEND_YIELD, row.get("IV_Put", 0) or 0) * (row.get("OI_Put", 0) or 0)
        for _, row in df.iterrows()
    )

    def ratio(a, b): return a / b if b else 0

    rows = [
        ("Put/Call OI Ratio", ratio(put_oi, call_oi)),
        ("PCR x Gamma", ratio(put_gamma, call_gamma)),
        ("PCR x Delta", ratio(put_delta, call_delta)),
        ("PCR x Vega", ratio(put_vega, call_vega)),
        ("PCR x Theta", ratio(put_theta, call_theta)),
        ("PCR x IV", ratio(put_iv_sum, call_iv_sum)),
        ("Weighted PCR Gamma", ratio(weighted_put_gamma, weighted_call_gamma)),
        ("Weighted PCR Vega", ratio(weighted_put_vega, weighted_call_vega)),
    ]

    win = ctk.CTkToplevel(root)
    win.title("Stats Breakdown")
    win.geometry("420x600")
    
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

    # Stats rows - side by side layout
    stats_frame = ctk.CTkFrame(win, fg_color="transparent")
    stats_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    # Create two columns
    labels_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
    labels_frame.pack(side="left", fill="y", padx=(0, 20))
    
    values_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
    values_frame.pack(side="left", fill="y")
    
    for label, value in rows:
        ctk.CTkLabel(
            labels_frame,
            text=label,
            anchor="w",
            width=200
        ).pack(anchor="w", pady=4)
        ctk.CTkLabel(
            values_frame,
            text=f"{value:.3f}",
            font=("Segoe UI", 16, "bold"),
            anchor="w",
            width=100
        ).pack(anchor="w", pady=4)
