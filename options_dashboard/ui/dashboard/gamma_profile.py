import customtkinter as ctk
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from scipy.stats import norm

from models.greeks import gamma
from utils.time import time_to_expiration
from config import RISK_FREE_RATE, DIVIDEND_YIELD


def calc_gamma_exposure(S, K, vol, T, r, q, opt_type, OI):
    """Calculate gamma exposure for a single option"""
    if T == 0 or vol == 0:
        return 0
    
    # Convert IV from percentage to decimal if needed
    if vol > 1:
        vol = vol / 100.0
    
    dp = (np.log(S / K) + (r - q + 0.5 * vol**2) * T) / (vol * np.sqrt(T))
    
    if opt_type == 'call':
        gamma_val = np.exp(-q * T) * norm.pdf(dp) / (S * vol * np.sqrt(T))
        return OI * 100 * S * S * 0.01 * gamma_val
    else:  # put
        # Gamma is same for calls and puts, but using put formula for consistency
        dm = dp - vol * np.sqrt(T)
        gamma_val = K * np.exp(-r * T) * norm.pdf(dm) / (S * S * vol * np.sqrt(T))
        return OI * 100 * S * S * 0.01 * gamma_val * -1  # Negative for puts


def is_third_friday(d):
    """Check if date is the third Friday of the month"""
    return d.weekday() == 4 and 15 <= d.day <= 21


def generate_gamma_profile(dashboard, symbol, state, expiration):
    """Generate gamma profile chart with gamma flip for the given symbol and expiration"""
    if not state or not state.exp_data_map:
        from ui import dialogs
        dialogs.warning("No Data", "No options data available for this ticker.")
        return
    
    # Get the data for the selected expiration
    if expiration not in state.exp_data_map:
        from ui import dialogs
        dialogs.warning("No Data", f"No data available for expiration {expiration}.")
        return
    
    df = state.exp_data_map[expiration]
    if df is None or df.empty:
        from ui import dialogs
        dialogs.warning("No Data", "No valid options data found for this expiration.")
        return
    
    # Get current spot price
    spot_price = state.price
    if spot_price <= 0:
        from ui import dialogs
        dialogs.warning("Invalid Price", "Invalid spot price for this ticker.")
        return
    
    # Calculate strike range (80% to 120% of spot)
    from_strike = 0.8 * spot_price
    to_strike = 1.2 * spot_price
    
    # Get today's date
    today_date = datetime.datetime.now()
    
    # Calculate time to expiration
    T = time_to_expiration(expiration)
    if T <= 0:
        # For 0DTE options, set to 1 day to avoid exclusion
        T = 1 / 262
    
    # Parse expiration date
    try:
        exp_datetime = datetime.datetime.strptime(expiration.split(":")[0], "%Y-%m-%d")
    except:
        exp_datetime = today_date
    
    # Prepare data rows
    all_rows = []
    for _, row in df.iterrows():
        strike = float(row.get("Strike", 0) or 0)
        if strike <= 0:
            continue
        
        call_iv = float(row.get("IV_Call", 0) or 0)
        put_iv = float(row.get("IV_Put", 0) or 0)
        call_oi = float(row.get("OI_Call", 0) or 0)
        put_oi = float(row.get("OI_Put", 0) or 0)
        
        all_rows.append({
            "Strike": strike,
            "CallIV": call_iv,
            "PutIV": put_iv,
            "CallOI": call_oi,
            "PutOI": put_oi,
            "ExpirationDate": exp_datetime,
            "daysTillExp": T,
            "ExpirationKey": expiration
        })
    
    if not all_rows:
        from ui import dialogs
        dialogs.warning("No Data", "No valid options data found.")
        return
    
    df = pd.DataFrame(all_rows)
    
    # Calculate gamma profile at different spot levels
    levels = np.linspace(from_strike, to_strike, 60)
    
    total_gamma = []
    
    # For each spot level, calculate gamma exposure
    for level in levels:
        df['callGammaEx'] = df.apply(
            lambda row: calc_gamma_exposure(
                level, row['Strike'], row['CallIV'], 
                row['daysTillExp'], RISK_FREE_RATE, DIVIDEND_YIELD, 
                "call", row['CallOI']
            ), axis=1
        )
        
        df['putGammaEx'] = df.apply(
            lambda row: calc_gamma_exposure(
                level, row['Strike'], row['PutIV'], 
                row['daysTillExp'], RISK_FREE_RATE, DIVIDEND_YIELD, 
                "put", row['PutOI']
            ), axis=1
        )
        
        # Total gamma (calls - puts, puts are already negative in calc_gamma_exposure)
        total_gamma.append(df['callGammaEx'].sum() + df['putGammaEx'].sum())
    
    # Convert to billions
    total_gamma = np.array(total_gamma) / 1e9
    
    # Find Gamma Flip Point (zero crossing)
    zero_cross_idx = np.where(np.diff(np.sign(total_gamma)))[0]
    
    if len(zero_cross_idx) > 0:
        neg_gamma = total_gamma[zero_cross_idx[0]]
        pos_gamma = total_gamma[zero_cross_idx[0] + 1]
        neg_strike = levels[zero_cross_idx[0]]
        pos_strike = levels[zero_cross_idx[0] + 1]
        
        zero_gamma = pos_strike - ((pos_strike - neg_strike) * pos_gamma / (pos_gamma - neg_gamma))
    else:
        zero_gamma = None
    
    # Create the chart window
    win = ctk.CTkToplevel(dashboard.root)
    win.geometry("1000x700")
    current_time = datetime.datetime.now().strftime('%I:%M %p')
    win.title(f"{symbol} Gamma Profile | {current_time}")
    
    # Ensure window stays in front
    win.lift()
    win.focus()
    win.attributes("-topmost", True)
    win.after(100, lambda: win.attributes("-topmost", False))
    
    # Create matplotlib figure
    fig = Figure(figsize=(10, 6), dpi=100)
    ax = fig.add_subplot(111)
    
    # Plot the gamma profile
    exp_date_str = expiration.split(":")[0]
    ax.plot(levels, total_gamma, label=f"Expiration: {exp_date_str}", linewidth=2)
    
    # Add vertical lines
    ax.axvline(x=spot_price, color='r', lw=2, label=f"Spot: ${spot_price:,.0f}")
    if zero_gamma:
        ax.axvline(x=zero_gamma, color='g', lw=2, label=f"Gamma Flip: ${zero_gamma:,.0f}")
    ax.axhline(y=0, color='grey', lw=1, linestyle='--')
    
    # Add shaded regions
    trans = ax.get_xaxis_transform()
    if zero_gamma:
        ax.fill_between(
            [from_strike, zero_gamma], 
            min(total_gamma), max(total_gamma), 
            facecolor='red', alpha=0.1, transform=trans
        )
        ax.fill_between(
            [zero_gamma, to_strike], 
            min(total_gamma), max(total_gamma), 
            facecolor='green', alpha=0.1, transform=trans
        )
    
    # Formatting
    chart_title = f"Gamma Exposure Profile, {symbol}, {today_date.strftime('%d %b %Y')}"
    ax.set_title(chart_title, fontweight="bold", fontsize=16)
    ax.set_xlabel('Index Price', fontweight="bold")
    ax.set_ylabel('Gamma Exposure ($ billions/1% move)', fontweight="bold")
    ax.set_xlim([from_strike, to_strike])
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Embed in tkinter window
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    toolbar = NavigationToolbar2Tk(canvas, win)
    toolbar.update()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    
    # Bring window to front
    win.update_idletasks()
    win.lift()
    win.focus()

