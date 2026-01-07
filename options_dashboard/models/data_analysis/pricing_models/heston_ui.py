import customtkinter as ctk
import datetime
import json
import os
import tkinter as tk
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from models.data_analysis.pricing_models.heston import heston_call_price
from models.data_analysis.pricing_models.heston_simulation import (
    simulate_heston_paths,
    calculate_implied_volatility_smile
)
from utils.time import time_to_expiration
from config import RISK_FREE_RATE, DIVIDEND_YIELD
from ui import dialogs


def get_heston_params_file_path():
    """Get the absolute path to the Heston parameters file"""
    # Get the data_analysis directory, then go to settings folder
    data_analysis_dir = Path(__file__).resolve().parent.parent
    return data_analysis_dir / "settings" / "heston_params.json"


# Factory default values (used for reset)
FACTORY_DEFAULTS = {
    "kappa": 2.0,
    "theta": 0.04,
    "sigma_v": 0.3,
    "rho": -0.7,
    "simulation_days": 30,
    "time_steps": 100
}

def load_heston_params():
    """Load Heston model parameters from JSON file"""
    params_path = get_heston_params_file_path()
    if os.path.exists(params_path):
        try:
            with open(params_path, "r") as f:
                params = json.load(f)
                return params
        except Exception as e:
            print(f"Failed to load Heston parameters: {e}")
    # Return defaults if file doesn't exist or fails to load
    return FACTORY_DEFAULTS.copy()


def save_heston_params(params):
    """Save Heston model parameters to JSON file"""
    try:
        params_path = get_heston_params_file_path()
        with open(params_path, "w") as f:
            json.dump(params, f, indent=2)
    except Exception as e:
        print(f"Failed to save Heston parameters: {e}")


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
    
    # Header frame with title and help button
    header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    header_frame.pack(fill="x", pady=(10, 20))
    
    # Title (left side)
    title_label = ctk.CTkLabel(
        header_frame,
        text=f"Heston Model Configuration - {symbol}",
        font=ctk.CTkFont(size=16, weight="bold")
    )
    title_label.pack(side="left", padx=(0, 10))
    
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
    
    # Load parameter values from JSON file
    saved_params = load_heston_params()
    default_kappa = saved_params.get("kappa", FACTORY_DEFAULTS["kappa"])  # Mean reversion speed
    default_theta = saved_params.get("theta", FACTORY_DEFAULTS["theta"])  # Long-run variance (20% vol squared)
    default_sigma_v = saved_params.get("sigma_v", FACTORY_DEFAULTS["sigma_v"])  # Vol of vol
    default_rho = saved_params.get("rho", FACTORY_DEFAULTS["rho"])  # Correlation
    default_days = saved_params.get("simulation_days", FACTORY_DEFAULTS["simulation_days"])
    default_steps = saved_params.get("time_steps", FACTORY_DEFAULTS["time_steps"])
    
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
    
    # Helper function to safely get IntVar value
    def safe_get_int(var, default=0):
        try:
            value = var.get()
            return int(value) if value != "" else default
        except (ValueError, tk.TclError):
            return default
    
    # Update value labels when sliders change and save parameters
    def update_kappa_label(value):
        params['kappa'][1].configure(text=f"{value:.2f}")
        try:
            save_heston_params({
                "kappa": value,
                "theta": theta_var.get(),
                "sigma_v": sigma_v_var.get(),
                "rho": rho_var.get(),
                "simulation_days": safe_get_int(days_var, default_days),
                "time_steps": safe_get_int(steps_var, default_steps)
            })
        except (ValueError, tk.TclError):
            pass  # Ignore errors when values are invalid
    
    def update_theta_label(value):
        params['theta'][1].configure(text=f"{value:.4f}")
        try:
            save_heston_params({
                "kappa": kappa_var.get(),
                "theta": value,
                "sigma_v": sigma_v_var.get(),
                "rho": rho_var.get(),
                "simulation_days": safe_get_int(days_var, default_days),
                "time_steps": safe_get_int(steps_var, default_steps)
            })
        except (ValueError, tk.TclError):
            pass
    
    def update_sigma_v_label(value):
        params['sigma_v'][1].configure(text=f"{value:.3f}")
        try:
            save_heston_params({
                "kappa": kappa_var.get(),
                "theta": theta_var.get(),
                "sigma_v": value,
                "rho": rho_var.get(),
                "simulation_days": safe_get_int(days_var, default_days),
                "time_steps": safe_get_int(steps_var, default_steps)
            })
        except (ValueError, tk.TclError):
            pass
    
    def update_rho_label(value):
        params['rho'][1].configure(text=f"{value:.3f}")
        try:
            save_heston_params({
                "kappa": kappa_var.get(),
                "theta": theta_var.get(),
                "sigma_v": sigma_v_var.get(),
                "rho": value,
                "simulation_days": safe_get_int(days_var, default_days),
                "time_steps": safe_get_int(steps_var, default_steps)
            })
        except (ValueError, tk.TclError):
            pass
    
    kappa_slider.configure(command=update_kappa_label)
    theta_slider.configure(command=update_theta_label)
    sigma_v_slider.configure(command=update_sigma_v_label)
    rho_slider.configure(command=update_rho_label)
    
    # Days selector for simulation
    days_label = ctk.CTkLabel(
        main_frame,
        text="Simulation Period (Days):",
        font=ctk.CTkFont(weight="bold")
    )
    days_label.pack(pady=(20, 5))
    
    days_var = ctk.IntVar(value=default_days)
    days_entry = ctk.CTkEntry(
        main_frame,
        textvariable=days_var,
        width=150
    )
    days_entry.pack(pady=5)
    
    # Save days when changed
    def update_days(*args):
        try:
            value = safe_get_int(days_var, default_days)
            if value > 0:
                save_heston_params({
                    "kappa": kappa_var.get(),
                    "theta": theta_var.get(),
                    "sigma_v": sigma_v_var.get(),
                    "rho": rho_var.get(),
                    "simulation_days": value,
                    "time_steps": safe_get_int(steps_var, default_steps)
                })
        except (ValueError, tk.TclError):
            pass  # Ignore errors when value is empty or invalid
    days_var.trace("w", update_days)
    
    # Number of time steps
    steps_label = ctk.CTkLabel(
        main_frame,
        text="Time Steps:",
        font=ctk.CTkFont(weight="bold")
    )
    steps_label.pack(pady=(10, 5))
    
    steps_var = ctk.IntVar(value=default_steps)
    steps_entry = ctk.CTkEntry(
        main_frame,
        textvariable=steps_var,
        width=150
    )
    steps_entry.pack(pady=5)
    
    # Save steps when changed
    def update_steps(*args):
        try:
            value = safe_get_int(steps_var, default_steps)
            if value > 0:
                save_heston_params({
                    "kappa": kappa_var.get(),
                    "theta": theta_var.get(),
                    "sigma_v": sigma_v_var.get(),
                    "rho": rho_var.get(),
                    "simulation_days": safe_get_int(days_var, default_days),
                    "time_steps": value
                })
        except (ValueError, tk.TclError):
            pass  # Ignore errors when value is empty or invalid
    steps_var.trace("w", update_steps)
    
    # Fixed seed option for reproducible results
    seed_frame = ctk.CTkFrame(main_frame)
    seed_frame.pack(pady=(20, 10))
    
    use_fixed_seed_var = ctk.BooleanVar(value=False)
    seed_checkbox = ctk.CTkCheckBox(
        seed_frame,
        text="Use Fixed Seed (for reproducible results)",
        variable=use_fixed_seed_var,
        font=ctk.CTkFont(weight="bold")
    )
    seed_checkbox.pack(pady=(10, 5))
    
    seed_label = ctk.CTkLabel(
        seed_frame,
        text="Seed Value:",
        font=ctk.CTkFont(weight="bold")
    )
    seed_label.pack(pady=(10, 5))
    
    seed_var = ctk.IntVar(value=42)
    seed_entry = ctk.CTkEntry(
        seed_frame,
        textvariable=seed_var,
        width=150,
        state="disabled"  # Disabled by default
    )
    seed_entry.pack(pady=5)
    
    # Enable/disable seed entry based on checkbox
    def toggle_seed_entry():
        if use_fixed_seed_var.get():
            seed_entry.configure(state="normal")
        else:
            seed_entry.configure(state="disabled")
    
    seed_checkbox.configure(command=toggle_seed_entry)
    
    # Reset to defaults function
    def reset_to_defaults():
        """Reset all parameters to factory default values"""
        # Temporarily disable auto-save to avoid multiple saves
        kappa_slider.configure(command=lambda v: None)
        theta_slider.configure(command=lambda v: None)
        sigma_v_slider.configure(command=lambda v: None)
        rho_slider.configure(command=lambda v: None)
        
        # Reset all values
        kappa_var.set(FACTORY_DEFAULTS["kappa"])
        theta_var.set(FACTORY_DEFAULTS["theta"])
        sigma_v_var.set(FACTORY_DEFAULTS["sigma_v"])
        rho_var.set(FACTORY_DEFAULTS["rho"])
        days_var.set(FACTORY_DEFAULTS["simulation_days"])
        steps_var.set(FACTORY_DEFAULTS["time_steps"])
        
        # Reset seed checkbox and value
        use_fixed_seed_var.set(False)
        seed_var.set(42)
        seed_entry.configure(state="disabled")
        
        # Update labels
        params['kappa'][1].configure(text=f"{FACTORY_DEFAULTS['kappa']:.2f}")
        params['theta'][1].configure(text=f"{FACTORY_DEFAULTS['theta']:.4f}")
        params['sigma_v'][1].configure(text=f"{FACTORY_DEFAULTS['sigma_v']:.3f}")
        params['rho'][1].configure(text=f"{FACTORY_DEFAULTS['rho']:.3f}")
        
        # Re-enable auto-save with proper callbacks
        kappa_slider.configure(command=update_kappa_label)
        theta_slider.configure(command=update_theta_label)
        sigma_v_slider.configure(command=update_sigma_v_label)
        rho_slider.configure(command=update_rho_label)
        
        # Save to JSON file
        save_heston_params(FACTORY_DEFAULTS.copy())
    
    # Help button function
    def show_help():
        """Show help window explaining Heston model parameters"""
        help_win = ctk.CTkToplevel(win)
        help_win.title("Heston Model Parameters Help")
        help_win.geometry("600x550")
        help_win.resizable(True, True)
        
        # Center the window
        help_win.update_idletasks()
        screen_w = help_win.winfo_screenwidth()
        screen_h = help_win.winfo_screenheight()
        win_w = help_win.winfo_width()
        win_h = help_win.winfo_height()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        help_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # Bring to front immediately
        help_win.lift()
        help_win.focus()
        help_win.attributes("-topmost", True)
        help_win.after(100, lambda: help_win.attributes("-topmost", False))
        
        # Create scrollable frame
        scrollable_frame = ctk.CTkScrollableFrame(help_win)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            scrollable_frame,
            text="Heston Model Parameters Guide",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(10, 20))
        
        # Helper function to create parameter sections
        def add_parameter_section(name, symbol, description, range_text, details=""):
            frame = ctk.CTkFrame(scrollable_frame)
            frame.pack(fill="x", pady=10, padx=10)
            
            # Parameter name and symbol
            header = ctk.CTkLabel(
                frame,
                text=f"{name} ({symbol})",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            header.pack(anchor="w", padx=15, pady=(15, 5))
            
            # Description
            desc_label = ctk.CTkLabel(
                frame,
                text=description,
                font=ctk.CTkFont(size=13),
                wraplength=550,
                justify="left"
            )
            desc_label.pack(anchor="w", padx=15, pady=(0, 5))
            
            # Ideal range
            range_label = ctk.CTkLabel(
                frame,
                text=f"Ideal Range: {range_text}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("#0066CC", "#4A9EFF")
            )
            range_label.pack(anchor="w", padx=15, pady=(5, 5))
            
            # Additional details if provided
            if details:
                details_label = ctk.CTkLabel(
                    frame,
                    text=details,
                    font=ctk.CTkFont(size=12),
                    wraplength=550,
                    justify="left",
                    text_color=("#666666", "#CCCCCC")
                )
                details_label.pack(anchor="w", padx=15, pady=(0, 15))
            else:
                # Add padding if no details
                ctk.CTkLabel(frame, text="").pack(pady=(0, 15))
        
        # Kappa parameter
        add_parameter_section(
            "Kappa",
            "κ",
            "Mean reversion speed - controls how quickly volatility returns to its long-run average (theta). Higher values mean faster mean reversion. This parameter determines the 'memory' of the volatility process.",
            "0.5 - 5.0 (typical: 1.0 - 3.0)",
            "• Low κ (< 1.0): Volatility changes slowly, more persistent\n• High κ (> 3.0): Volatility reverts quickly to long-run level\n• Very high κ can cause numerical instability"
        )
        
        # Theta parameter
        add_parameter_section(
            "Theta",
            "θ",
            "Long-run variance - the average variance that volatility tends to revert to over the long term. This is the 'equilibrium' level of variance in the model.",
            "0.01 - 0.20 (typical: 0.02 - 0.10)",
            "• Represents annualized variance (not volatility)\n• θ = 0.04 means long-run volatility ≈ 20% (√0.04 = 0.20)\n• Should match the asset's historical volatility characteristics"
        )
        
        # Sigma_v parameter
        add_parameter_section(
            "Sigma_v",
            "σ_v",
            "Volatility of volatility (vol-of-vol) - controls how much the variance itself can fluctuate. Higher values create more volatility clustering and fat tails in returns.",
            "0.1 - 0.8 (typical: 0.2 - 0.5)",
            "• Low σ_v: Variance changes smoothly\n• High σ_v: Variance can spike dramatically (creates volatility smiles)\n• Too high (> 1.0) can violate Feller condition (2κθ > σ_v²)"
        )
        
        # Rho parameter
        add_parameter_section(
            "Rho",
            "ρ",
            "Correlation between stock price and variance - determines the leverage effect. Negative values mean when stock price falls, volatility tends to increase (typical for equities).",
            "-0.9 to -0.3 (typical: -0.5 to -0.7)",
            "• ρ < 0: Negative correlation (equity markets)\n• ρ ≈ 0: No correlation\n• ρ > 0: Positive correlation (rare, some commodities)\n• Extreme values (|ρ| > 0.9) can cause numerical issues"
        )
        
        # Kappa/Theta ratio section
        ratio_frame = ctk.CTkFrame(scrollable_frame)
        ratio_frame.pack(fill="x", pady=10, padx=10)
        
        ratio_header = ctk.CTkLabel(
            ratio_frame,
            text="Kappa/Theta Ratio (κ/θ)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        ratio_header.pack(anchor="w", padx=15, pady=(15, 5))
        
        ratio_desc = ctk.CTkLabel(
            ratio_frame,
            text="The ratio of kappa to theta is important for understanding volatility dynamics:",
            font=ctk.CTkFont(size=13),
            wraplength=550,
            justify="left"
        )
        ratio_desc.pack(anchor="w", padx=15, pady=(0, 10))
        
        ratio_points = [
            "• High κ/θ ratio (> 50): Fast mean reversion, volatility quickly returns to long-run level",
            "• Medium κ/θ ratio (10-50): Balanced behavior, typical for most equity markets",
            "• Low κ/θ ratio (< 10): Slow mean reversion, volatility persists longer",
            "• The ratio affects the shape of the volatility smile - higher ratios create steeper smiles"
        ]
        
        for point in ratio_points:
            point_label = ctk.CTkLabel(
                ratio_frame,
                text=point,
                font=ctk.CTkFont(size=12),
                wraplength=550,
                justify="left",
                anchor="w"
            )
            point_label.pack(anchor="w", padx=25, pady=2)
        
        ctk.CTkLabel(ratio_frame, text="").pack(pady=(0, 15))
        
        # Random Seed section
        seed_frame = ctk.CTkFrame(scrollable_frame)
        seed_frame.pack(fill="x", pady=10, padx=10)
        
        seed_header = ctk.CTkLabel(
            seed_frame,
            text="Random Seed",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        seed_header.pack(anchor="w", padx=15, pady=(15, 5))
        
        seed_desc = ctk.CTkLabel(
            seed_frame,
            text="The random seed controls the reproducibility of the Monte Carlo simulation:",
            font=ctk.CTkFont(size=13),
            wraplength=550,
            justify="left"
        )
        seed_desc.pack(anchor="w", padx=15, pady=(0, 10))
        
        seed_points = [
            "• Without fixed seed: Each simulation generates different random paths (default behavior)",
            "• With fixed seed: Same seed + same parameters = identical simulation results",
            "• Useful for: Comparing parameter changes, debugging, reproducible research",
            "• Seed value: Any integer (default: 42). Different seeds produce different but valid paths",
            "• Note: The volatility smile is deterministic and doesn't depend on the seed"
        ]
        
        for point in seed_points:
            point_label = ctk.CTkLabel(
                seed_frame,
                text=point,
                font=ctk.CTkFont(size=12),
                wraplength=550,
                justify="left",
                anchor="w"
            )
            point_label.pack(anchor="w", padx=25, pady=2)
        
        ctk.CTkLabel(seed_frame, text="").pack(pady=(0, 15))
        
        # Simulation Period section
        period_frame = ctk.CTkFrame(scrollable_frame)
        period_frame.pack(fill="x", pady=10, padx=10)
        
        period_header = ctk.CTkLabel(
            period_frame,
            text="Simulation Period (Days)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        period_header.pack(anchor="w", padx=15, pady=(15, 5))
        
        period_desc = ctk.CTkLabel(
            period_frame,
            text="The number of days into the future to simulate the stock price and volatility paths:",
            font=ctk.CTkFont(size=13),
            wraplength=550,
            justify="left"
        )
        period_desc.pack(anchor="w", padx=15, pady=(0, 10))
        
        period_points = [
            "• Typical range: 7-90 days (1 week to 3 months)",
            "• Longer periods show more volatility mean reversion behavior",
            "• Shorter periods focus on near-term dynamics",
            "• Default: 30 days (approximately 1 month)",
            "• The simulation shows how price and volatility evolve over this time horizon"
        ]
        
        for point in period_points:
            point_label = ctk.CTkLabel(
                period_frame,
                text=point,
                font=ctk.CTkFont(size=12),
                wraplength=550,
                justify="left",
                anchor="w"
            )
            point_label.pack(anchor="w", padx=25, pady=2)
        
        ctk.CTkLabel(period_frame, text="").pack(pady=(0, 15))
        
        # Time Steps section
        steps_frame = ctk.CTkFrame(scrollable_frame)
        steps_frame.pack(fill="x", pady=10, padx=10)
        
        steps_header = ctk.CTkLabel(
            steps_frame,
            text="Time Steps",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        steps_header.pack(anchor="w", padx=15, pady=(15, 5))
        
        steps_desc = ctk.CTkLabel(
            steps_frame,
            text="The number of discrete time steps used in the Monte Carlo simulation:",
            font=ctk.CTkFont(size=13),
            wraplength=550,
            justify="left"
        )
        steps_desc.pack(anchor="w", padx=15, pady=(0, 10))
        
        steps_points = [
            "• More steps = smoother, more accurate simulation (but slower)",
            "• Fewer steps = faster computation but less precise paths",
            "• Typical range: 50-200 steps",
            "• Default: 100 steps (good balance of accuracy and speed)",
            "• For daily simulation over 30 days, 100 steps ≈ 0.3 days per step",
            "• Higher values recommended for longer simulation periods"
        ]
        
        for point in steps_points:
            point_label = ctk.CTkLabel(
                steps_frame,
                text=point,
                font=ctk.CTkFont(size=12),
                wraplength=550,
                justify="left",
                anchor="w"
            )
            point_label.pack(anchor="w", padx=25, pady=2)
        
        ctk.CTkLabel(steps_frame, text="").pack(pady=(0, 15))
        
        # Close button
        close_btn = ctk.CTkButton(
            scrollable_frame,
            text="Close",
            command=help_win.destroy,
            width=150
        )
        close_btn.pack(pady=20)
        
        # Bring help window to front (already done above, but ensure it stays)
        help_win.after(50, lambda: help_win.lift())
        help_win.after(150, lambda: help_win.lift())
    
    # Help button (in header, top right)
    help_btn = ctk.CTkButton(
        header_frame,
        text="Help",
        command=show_help,
        width=80,
        height=30,
        font=ctk.CTkFont(size=11),
        fg_color=("gray70", "gray30")
    )
    help_btn.pack(side="right")
    
    # Reset button
    reset_btn = ctk.CTkButton(
        main_frame,
        text="Reset to Defaults",
        command=reset_to_defaults,
        width=200,
        height=35,
        font=ctk.CTkFont(size=12),
        fg_color=("gray70", "gray30")
    )
    reset_btn.pack(pady=(5, 5))
    
    # Generate button
    def generate_heston_chart():
        """Generate Heston model charts: volatility smile and dynamics"""
        try:
            # Get parameters
            kappa = kappa_var.get()
            theta = theta_var.get()
            sigma_v = sigma_v_var.get()
            rho = rho_var.get()
            
            # Safely get days and steps with validation
            try:
                n_days = safe_get_int(days_var, default_days)
                n_steps = safe_get_int(steps_var, default_steps)
            except (ValueError, tk.TclError):
                dialogs.warning("Invalid Input", "Days and steps must be valid numbers.")
                return
            
            if n_days <= 0 or n_steps <= 0:
                dialogs.warning("Invalid Input", "Days and steps must be positive.")
                return
            
            # Get market data
            S0 = state.price
            T_exp = time_to_expiration(exp)
            r = RISK_FREE_RATE
            q = DIVIDEND_YIELD
            
            if S0 <= 0 or T_exp <= 0:
                dialogs.warning("Invalid Data", "Invalid spot price or expiration date.")
                return
            
            # Get initial variance from market IV
            df = state.exp_data_map[exp]
            if df is None or df.empty:
                dialogs.warning("No Data", "No options data available for this expiration.")
                return
            
            # Calculate average IV for initial variance
            ivs = []
            for row in df.itertuples(index=False):
                call_iv = float(getattr(row, 'IV_Call', 0) or 0)
                put_iv = float(getattr(row, 'IV_Put', 0) or 0)
                if call_iv > 1:
                    call_iv /= 100.0
                if put_iv > 1:
                    put_iv /= 100.0
                if call_iv > 0:
                    ivs.append(call_iv)
                if put_iv > 0:
                    ivs.append(put_iv)
            
            if not ivs:
                dialogs.warning("No Data", "No implied volatility data available.")
                return
            
            v0 = np.mean([iv**2 for iv in ivs])  # Initial variance
            
            # Convert days to years for simulation
            T_sim = n_days / 365.0
            
            # Simulate Heston paths
            # Use fixed seed if checkbox is enabled, otherwise None for random results
            random_seed = None
            if use_fixed_seed_var.get():
                try:
                    random_seed = safe_get_int(seed_var, 42)
                except (ValueError, tk.TclError):
                    random_seed = 42  # Default seed if invalid
            
            times, S_paths, v_paths = simulate_heston_paths(
                S0, v0, T_sim, r, q, kappa, theta, sigma_v, rho, n_steps, n_paths=1, random_seed=random_seed
            )
            
            # Convert times to days
            times_days = times * 365.0
            
            # Get strikes for volatility smile
            strikes = []
            for row in df.itertuples(index=False):
                K = float(row.Strike) if hasattr(row, 'Strike') else 0
                if K > 0:
                    strikes.append(K)
            
            if not strikes:
                dialogs.warning("No Data", "No strike prices available.")
                return
            
            strikes = sorted(set(strikes))
            # Limit to reasonable range around current price
            strikes = [K for K in strikes if 0.5 * S0 <= K <= 1.5 * S0]
            
            if len(strikes) < 3:
                dialogs.warning("No Data", "Not enough strikes for volatility smile.")
                return
            
            # Calculate volatility smile at current time
            smile_strikes, smile_ivs = calculate_implied_volatility_smile(
                S0, strikes, T_exp, r, q, v0, kappa, theta, sigma_v, rho, heston_call_price
            )
            
            # Create chart window with two subplots
            chart_win = ctk.CTkToplevel(dashboard.root)
            chart_win.geometry("1200x800")
            current_time = datetime.datetime.now().strftime('%I:%M %p')
            exp_date = exp.split(":")[0]
            chart_win.title(f"{symbol} Heston Model Analysis - {exp_date} | {current_time}")
            
            # Create matplotlib figure with subplots
            fig = Figure(figsize=(12, 8), dpi=100)
            
            # Plot 1: Volatility Smile
            ax1 = fig.add_subplot(2, 2, 1)
            ax1.plot(smile_strikes, smile_ivs * 100, 'o-', linewidth=2, markersize=4, color='blue')
            ax1.axvline(x=S0, color='red', linestyle='--', linewidth=1, label=f'Spot: ${S0:.2f}')
            ax1.set_title("Implied Volatility Smile", fontweight="bold", fontsize=12)
            ax1.set_xlabel("Strike Price", fontweight="bold")
            ax1.set_ylabel("Implied Volatility (%)", fontweight="bold")
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Plot 2: Stock Price Dynamics
            ax2 = fig.add_subplot(2, 2, 2)
            ax2.plot(times_days, S_paths[0], linewidth=2, color='green', label='Stock Price')
            ax2.axhline(y=S0, color='red', linestyle='--', linewidth=1, label=f'Initial: ${S0:.2f}')
            ax2.set_title("Stock Price Dynamics", fontweight="bold", fontsize=12)
            ax2.set_xlabel("Time (Days)", fontweight="bold")
            ax2.set_ylabel("Stock Price ($)", fontweight="bold")
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # Plot 3: Volatility Dynamics
            ax3 = fig.add_subplot(2, 2, 3)
            # Convert variance to volatility (annualized)
            vol_paths = np.sqrt(v_paths[0]) * np.sqrt(252) * 100  # Annualized, in percentage
            ax3.plot(times_days, vol_paths, linewidth=2, color='purple', label='Volatility')
            initial_vol = np.sqrt(v0) * np.sqrt(252) * 100
            ax3.axhline(y=initial_vol, color='red', linestyle='--', linewidth=1, label=f'Initial: {initial_vol:.2f}%')
            long_run_vol = np.sqrt(theta) * np.sqrt(252) * 100
            ax3.axhline(y=long_run_vol, color='orange', linestyle='--', linewidth=1, label=f'Long-run: {long_run_vol:.2f}%')
            ax3.set_title("Volatility Dynamics", fontweight="bold", fontsize=12)
            ax3.set_xlabel("Time (Days)", fontweight="bold")
            ax3.set_ylabel("Volatility (%)", fontweight="bold")
            ax3.grid(True, alpha=0.3)
            ax3.legend()
            
            # Plot 4: Variance Path
            ax4 = fig.add_subplot(2, 2, 4)
            ax4.plot(times_days, v_paths[0], linewidth=2, color='blue', label='Variance')
            ax4.axhline(y=v0, color='red', linestyle='--', linewidth=1, label=f'Initial: {v0:.4f}')
            ax4.axhline(y=theta, color='orange', linestyle='--', linewidth=1, label=f'Long-run: {theta:.4f}')
            ax4.set_title("Variance Dynamics", fontweight="bold", fontsize=12)
            ax4.set_xlabel("Time (Days)", fontweight="bold")
            ax4.set_ylabel("Variance", fontweight="bold")
            ax4.grid(True, alpha=0.3)
            ax4.legend()
            
            fig.suptitle(
                f"{symbol} Heston Model Analysis ({exp_date}) - {current_time}\n"
                f"κ={kappa:.2f}, θ={theta:.4f}, σ_v={sigma_v:.3f}, ρ={rho:.3f}",
                fontweight="bold",
                fontsize=14
            )
            fig.tight_layout(rect=[0, 0.03, 1, 0.97])
            
            # Embed in tkinter window
            canvas = FigureCanvasTkAgg(fig, master=chart_win)
            canvas.draw()
            toolbar = NavigationToolbar2Tk(canvas, chart_win)
            toolbar.update()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # Bring window to front (but don't block other windows)
            chart_win.update_idletasks()
            chart_win.lift()
            chart_win.focus()
            # Ensure it comes to front after rendering, but don't use grab_set or topmost
            # This allows other windows to be accessed while still bringing this one forward
            chart_win.after(50, lambda: chart_win.lift())
            chart_win.after(150, lambda: chart_win.lift())
            
            # Save parameters after generating chart (in case they were changed)
            save_heston_params({
                "kappa": kappa,
                "theta": theta,
                "sigma_v": sigma_v,
                "rho": rho,
                "simulation_days": n_days,
                "time_steps": n_steps
            })
            
        except Exception as e:
            import traceback
            dialogs.error("Error", f"Failed to generate Heston chart: {str(e)}\n\n{traceback.format_exc()}")
    
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

