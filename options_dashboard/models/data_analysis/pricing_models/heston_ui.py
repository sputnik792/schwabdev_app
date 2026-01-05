import customtkinter as ctk
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from models.data_analysis.pricing_models.heston import heston_greeks
from utils.time import time_to_expiration
from config import RISK_FREE_RATE, DIVIDEND_YIELD
from ui import dialogs


def open_heston_window(dashboard):
    """Open the Heston model configuration window"""
    # Check if we're in single view or multi view
    is_single_view = (hasattr(dashboard, 'single_view') and 
                     dashboard.single_view is not None and 
                     dashboard.single_view.winfo_viewable())
    
    if is_single_view:
        if not hasattr(dashboard, 'single_view_symbol'):
            dialogs.warning("No Ticker", "Please enter and fetch a ticker symbol first.")
            return
        symbol = dashboard.single_view_symbol
    else:
        if not hasattr(dashboard, 'notebook'):
            dialogs.warning("No Tabs", "No tabs available.")
            return
        tab_id = dashboard.notebook.select()
        if not tab_id:
            dialogs.warning("No Tab Selected", "Please select a tab.")
            return
        symbol = dashboard.notebook.tab(tab_id, "text")
    
    state = dashboard.ticker_data.get(symbol)
    if not state:
        dialogs.warning("No Data", "No data available for this ticker.")
        return
    
    # Get the selected expiration date
    if is_single_view:
        ticker_tabs_key = f"_single_{symbol}"
    else:
        ticker_tabs_key = symbol
    
    ui = dashboard.ticker_tabs.get(ticker_tabs_key)
    if not ui:
        dialogs.warning("No Data", "No UI data available for this ticker.")
        return
    
    exp = ui["exp_var"].get()
    if not exp:
        dialogs.warning("No Expiration", "Please select an expiration date.")
        return
    
    # Create the Heston configuration window
    win = ctk.CTkToplevel(dashboard.root)
    win.title(f"Heston Model - {symbol}")
    win.geometry("500x600")
    win.resizable(True, True)
    
    # Center the window
    win.update_idletasks()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    win_w = win.winfo_width()
    win_h = win.winfo_height()
    x = (screen_w // 2) - (win_w // 2)
    y = (screen_h // 2) - (win_h // 2)
    win.geometry(f"{win_w}x{win_h}+{x}+{y}")
    
    # Create scrollable frame
    scrollable_frame = ctk.CTkScrollableFrame(win)
    scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    # Main container
    main_frame = ctk.CTkFrame(scrollable_frame)
    main_frame.pack(fill="both", expand=True)
    
    # Title
    title_label = ctk.CTkLabel(
        main_frame,
        text=f"Heston Model Configuration - {symbol}",
        font=ctk.CTkFont(size=16, weight="bold")
    )
    title_label.pack(pady=(10, 20))
    
    # Expiration info
    exp_label = ctk.CTkLabel(
        main_frame,
        text=f"Expiration: {exp.split(':')[0]}",
        font=ctk.CTkFont(size=12)
    )
    exp_label.pack(pady=(0, 20))
    
    # Parameters frame
    params_frame = ctk.CTkFrame(main_frame)
    params_frame.pack(fill="x", pady=10)
    
    # Default parameter values (good defaults for Heston)
    default_kappa = 2.0  # Mean reversion speed
    default_theta = 0.04  # Long-run variance (20% vol squared)
    default_sigma_v = 0.3  # Vol of vol
    default_rho = -0.7  # Correlation
    
    # Parameter sliders
    params = {}
    
    # Kappa (mean reversion speed)
    kappa_label = ctk.CTkLabel(params_frame, text="κ (Kappa - Mean Reversion Speed):", font=ctk.CTkFont(weight="bold"))
    kappa_label.pack(pady=(10, 5))
    kappa_var = ctk.DoubleVar(value=default_kappa)
    kappa_slider = ctk.CTkSlider(
        params_frame,
        from_=0.1,
        to=10.0,
        variable=kappa_var,
        number_of_steps=99
    )
    kappa_slider.pack(fill="x", padx=20, pady=5)
    kappa_value_label = ctk.CTkLabel(params_frame, text=f"{default_kappa:.2f}")
    kappa_value_label.pack()
    params['kappa'] = (kappa_var, kappa_value_label)
    
    # Theta (long-run variance)
    theta_label = ctk.CTkLabel(params_frame, text="θ (Theta - Long-Run Variance):", font=ctk.CTkFont(weight="bold"))
    theta_label.pack(pady=(10, 5))
    theta_var = ctk.DoubleVar(value=default_theta)
    theta_slider = ctk.CTkSlider(
        params_frame,
        from_=0.01,
        to=0.20,
        variable=theta_var,
        number_of_steps=190
    )
    theta_slider.pack(fill="x", padx=20, pady=5)
    theta_value_label = ctk.CTkLabel(params_frame, text=f"{default_theta:.4f}")
    theta_value_label.pack()
    params['theta'] = (theta_var, theta_value_label)
    
    # Sigma_v (vol of vol)
    sigma_v_label = ctk.CTkLabel(params_frame, text="σ_v (Sigma_v - Vol of Vol):", font=ctk.CTkFont(weight="bold"))
    sigma_v_label.pack(pady=(10, 5))
    sigma_v_var = ctk.DoubleVar(value=default_sigma_v)
    sigma_v_slider = ctk.CTkSlider(
        params_frame,
        from_=0.01,
        to=1.0,
        variable=sigma_v_var,
        number_of_steps=99
    )
    sigma_v_slider.pack(fill="x", padx=20, pady=5)
    sigma_v_value_label = ctk.CTkLabel(params_frame, text=f"{default_sigma_v:.3f}")
    sigma_v_value_label.pack()
    params['sigma_v'] = (sigma_v_var, sigma_v_value_label)
    
    # Rho (correlation)
    rho_label = ctk.CTkLabel(params_frame, text="ρ (Rho - Correlation):", font=ctk.CTkFont(weight="bold"))
    rho_label.pack(pady=(10, 5))
    rho_var = ctk.DoubleVar(value=default_rho)
    rho_slider = ctk.CTkSlider(
        params_frame,
        from_=-0.99,
        to=0.99,
        variable=rho_var,
        number_of_steps=198
    )
    rho_slider.pack(fill="x", padx=20, pady=5)
    rho_value_label = ctk.CTkLabel(params_frame, text=f"{default_rho:.3f}")
    rho_value_label.pack()
    params['rho'] = (rho_var, rho_value_label)
    
    # Update value labels when sliders change
    def update_kappa_label(value):
        params['kappa'][1].configure(text=f"{value:.2f}")
    def update_theta_label(value):
        params['theta'][1].configure(text=f"{value:.4f}")
    def update_sigma_v_label(value):
        params['sigma_v'][1].configure(text=f"{value:.3f}")
    def update_rho_label(value):
        params['rho'][1].configure(text=f"{value:.3f}")
    
    kappa_slider.configure(command=update_kappa_label)
    theta_slider.configure(command=update_theta_label)
    sigma_v_slider.configure(command=update_sigma_v_label)
    rho_slider.configure(command=update_rho_label)
    
    # Greek selector
    greek_label = ctk.CTkLabel(
        main_frame,
        text="Select Greek:",
        font=ctk.CTkFont(weight="bold")
    )
    greek_label.pack(pady=(20, 5))
    
    greek_var = ctk.StringVar(value="gamma")
    greek_dropdown = ctk.CTkOptionMenu(
        main_frame,
        variable=greek_var,
        values=["gamma", "vega", "vanna", "charm"],
        width=200
    )
    greek_dropdown.pack(pady=5)
    
    # Generate button
    def generate_heston_chart():
        """Generate Heston model chart"""
        try:
            # Get parameters
            kappa = kappa_var.get()
            theta = theta_var.get()
            sigma_v = sigma_v_var.get()
            rho = rho_var.get()
            selected_greek = greek_var.get()
            
            # Get market data
            S = state.price
            T = time_to_expiration(exp)
            r = RISK_FREE_RATE
            q = DIVIDEND_YIELD
            
            if S <= 0 or T <= 0:
                dialogs.warning("Invalid Data", "Invalid spot price or expiration date.")
                return
            
            # Get options data
            df = state.exp_data_map[exp]
            if df is None or df.empty:
                dialogs.warning("No Data", "No options data available for this expiration.")
                return
            
            # Calculate Heston Greeks for each strike
            exposure_rows = []
            
            for row in df.itertuples(index=False):
                K = float(row.Strike) if hasattr(row, 'Strike') else 0
                if K <= 0:
                    continue
                
                # Use average IV or call IV as v0 (initial variance)
                call_iv = float(getattr(row, 'IV_Call', 0) or 0)
                put_iv = float(getattr(row, 'IV_Put', 0) or 0)
                
                # Convert IV from percentage to decimal if needed
                if call_iv > 1:
                    call_iv /= 100.0
                if put_iv > 1:
                    put_iv /= 100.0
                
                # Use average IV or whichever is available
                if call_iv > 0 and put_iv > 0:
                    v0 = ((call_iv**2 + put_iv**2) / 2.0)
                elif call_iv > 0:
                    v0 = call_iv**2
                elif put_iv > 0:
                    v0 = put_iv**2
                else:
                    continue
                
                # Calculate Greek for calls
                if call_iv > 0:
                    try:
                        greek_val = heston_greeks(
                            S, K, T, r, q,
                            v0, kappa, theta, sigma_v, rho,
                            greek=selected_greek
                        )
                        call_oi = float(getattr(row, 'OI_Call', 0) or 0)
                        exposure = greek_val * call_oi * 100  # Contract multiplier
                        exposure_rows.append({
                            "Strike": K,
                            "Type": "CALL",
                            "Exposure": exposure
                        })
                    except Exception as e:
                        continue
                
                # Calculate Greek for puts
                if put_iv > 0:
                    try:
                        greek_val = heston_greeks(
                            S, K, T, r, q,
                            v0, kappa, theta, sigma_v, rho,
                            greek=selected_greek
                        )
                        put_oi = float(getattr(row, 'OI_Put', 0) or 0)
                        exposure = -greek_val * put_oi * 100  # Negative for puts
                        exposure_rows.append({
                            "Strike": K,
                            "Type": "PUT",
                            "Exposure": exposure
                        })
                    except Exception as e:
                        continue
            
            if not exposure_rows:
                dialogs.warning("No Data", "Could not calculate Heston Greeks. Check parameters.")
                return
            
            # Create chart
            df_plot = pd.DataFrame(exposure_rows)
            df_plot["Exposure_Bn"] = df_plot["Exposure"] / 1e9
            
            # Create chart window
            chart_win = ctk.CTkToplevel(dashboard.root)
            chart_win.geometry("950x700")
            current_time = datetime.datetime.now().strftime('%I:%M %p')
            exp_date = exp.split(":")[0]
            chart_win.title(f"{symbol} Heston {selected_greek.capitalize()} Exposure - {exp_date} | {current_time}")
            
            # Create matplotlib figure
            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)
            
            # Plot calls and puts
            calls = df_plot[df_plot["Type"] == "CALL"]
            puts = df_plot[df_plot["Type"] == "PUT"]
            
            if not calls.empty:
                ax.bar(calls["Strike"], calls["Exposure_Bn"], width=1, label="CALL", color="green", alpha=0.7)
            if not puts.empty:
                ax.bar(puts["Strike"], puts["Exposure_Bn"], width=1, label="PUT", color="red", alpha=0.7)
            
            # Formatting
            ax.set_title(
                f"{symbol} Heston {selected_greek.capitalize()} Exposure ({exp_date}) - {current_time}",
                fontweight="bold",
                fontsize=14
            )
            ax.set_xlabel("Strike Price", fontweight="bold")
            ax.set_ylabel(f"{selected_greek.capitalize()} Exposure ($ billions)", fontweight="bold")
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Embed in tkinter window
            canvas = FigureCanvasTkAgg(fig, master=chart_win)
            canvas.draw()
            toolbar = NavigationToolbar2Tk(canvas, chart_win)
            toolbar.update()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # Bring window to front
            chart_win.update_idletasks()
            chart_win.lift()
            chart_win.focus()
            
        except Exception as e:
            dialogs.error("Error", f"Failed to generate Heston chart: {str(e)}")
    
    generate_btn = ctk.CTkButton(
        main_frame,
        text="Generate Heston Chart",
        command=generate_heston_chart,
        width=200,
        height=40,
        font=ctk.CTkFont(size=14, weight="bold")
    )
    generate_btn.pack(pady=20)
    
    # Close button
    close_btn = ctk.CTkButton(
        main_frame,
        text="Close",
        command=win.destroy,
        width=150
    )
    close_btn.pack(pady=10)
    
    # Ensure window stays in front after all widgets are packed
    win.update_idletasks()
    win.lift()
    win.focus()
    win.attributes("-topmost", True)
    win.after(100, lambda: win.attributes("-topmost", False))
    win.after(200, lambda: (win.lift(), win.focus()))

