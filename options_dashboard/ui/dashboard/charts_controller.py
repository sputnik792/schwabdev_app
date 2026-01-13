import customtkinter as ctk
import datetime
import tkinter as tk
from tkinter import ttk
import pandas as pd
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
    # Initialize tracking sets if needed (do this first for all views)
    if not hasattr(self, '_generating_charts'):
        self._generating_charts = set()
    if not hasattr(self, '_chart_windows'):
        self._chart_windows = []
    
    # Check if we're in single view mode
    is_single_view = (hasattr(self, 'single_view') and 
                      self.single_view is not None and 
                      self.single_view.winfo_viewable())
    
    if is_single_view:
        # Single view mode - use single_view_symbol
        if not hasattr(self, 'single_view_symbol'):
            dialogs.warning("No Ticker", "Please enter and fetch a ticker symbol first.")
            return
        
        symbol = self.single_view_symbol
        # Check for data with base symbol first, then try with "(CSV)" suffix
        # (CSV data is stored with display_symbol which includes "(CSV)")
        state = self.ticker_data.get(symbol)
        if not state:
            # Try with "(CSV)" suffix for CSV-loaded data
            csv_symbol = f"{symbol} (CSV)"
            state = self.ticker_data.get(csv_symbol)
            if state:
                symbol = csv_symbol  # Use CSV symbol for lookup
        
        if not state:
            dialogs.warning("No Data", "Please fetch data first.")
            return
        
        # Single view entries use the key format "_single_{symbol}"
        # Use base symbol (without "(CSV)") for the UI key
        base_symbol = symbol.replace(" (CSV)", "")
        single_view_key = f"_single_{base_symbol}"
        ui = self.ticker_tabs.get(single_view_key)
        if not ui:
            dialogs.warning("No Data", "Please fetch data first.")
            return
        
        exp = ui["exp_var"].get()
        if not exp:
            dialogs.warning("No Expiration", "Please select an expiration date.")
            return
        
        # Create chart key - use base symbol (without "(CSV)") and exp to catch duplicate button clicks
        # (spot_override will be None for button clicks, so we can use a simpler key)
        chart_key = (base_symbol, exp, spot_override if spot_override is not None else state.price)
        
        # Check if we're already generating this exact chart - do this BEFORE any processing
        if chart_key in self._generating_charts:
            # Already generating this chart, skip to prevent duplicates
            return
        
        # Mark as generating IMMEDIATELY to prevent duplicate calls
        # This must happen before any async operations or delays
        self._generating_charts.add(chart_key)
    else:
        # Multi view mode - use notebook
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
    # Use itertuples() instead of iterrows() for better performance
    df = state.exp_data_map[exp]
    for row in df.itertuples(index=False):
        K = float(row.Strike) if hasattr(row, 'Strike') else 0
        if K <= 0:
            continue

        for opt in ("CALL", "PUT"):
            # Column names are IV_Call, OI_Call, IV_Put, OI_Put (capital C/P)
            opt_key = opt.capitalize()  # "CALL" -> "Call", "PUT" -> "Put"
            iv_attr = f"IV_{opt_key}"
            oi_attr = f"OI_{opt_key}"
            iv = float(getattr(row, iv_attr, 0) or 0)
            oi = float(getattr(row, oi_attr, 0) or 0)
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
        60,  # Reduced from 120 to 60 for better performance
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
        # Set meaningful title based on chart content
        exp_date = exp.split(":")[0]  # Get just the date part
        model_name = self.model_var.get()
        current_time = datetime.datetime.now().strftime('%I:%M %p')
        win.title(f"{symbol} {model_name} Exposure - {exp_date} | {current_time}")
        
        # Initialize chart windows tracking if not exists
        if not hasattr(self, '_chart_windows'):
            self._chart_windows = []
        
        # Store window reference
        self._chart_windows.append(win)
        
        # Update clear graphs button state
        if hasattr(self, 'update_clear_graphs_button_state'):
            self.update_clear_graphs_button_state()
        
        # Update focus bar
        if hasattr(self, 'update_focus_bar'):
            self.update_focus_bar()
        
        # Embed the chart
        embed_matplotlib_chart(
            win,
            df_plot,
            symbol,
            exp_date,
            model_name,
            total,
            zero_gamma
        )
        
        # Bring window to front immediately after embedding
        win.update_idletasks()
        win.lift()
        win.focus()
        
        # Bring ALL chart windows to front AFTER chart is embedded
        # (this ensures previous charts don't get pushed behind)
        def bring_all_charts_front():
            if hasattr(self, '_chart_windows') and self._chart_windows:
                for chart_win in self._chart_windows:
                    try:
                        if chart_win.winfo_exists():
                            chart_win.lift()
                            chart_win.focus()
                    except:
                        pass
                # Focus the most recently created window
                try:
                    if win.winfo_exists():
                        win.lift()
                        win.focus()
                except:
                    pass
        
        # Bring to front after delays to ensure they stay
        win.after(50, bring_all_charts_front)
        win.after(150, bring_all_charts_front)
        win.after(300, bring_all_charts_front)
        win.after(500, bring_all_charts_front)
        
        # For single view, remove from generating set after a delay
        if is_single_view:
            def clear_generating_flag():
                if hasattr(self, '_generating_charts') and chart_key in self._generating_charts:
                    self._generating_charts.remove(chart_key)
            # Clear the flag after chart is fully rendered
            win.after(1000, clear_generating_flag)
            
            # Don't create slider for single view - it causes infinite loops
            # User can click the button again if they want to change spot price
        else:
            # For multi view, create slider immediately
            if not (hasattr(self, '_generating_chart_group') and self._generating_chart_group):
                for w in self.sidebar.winfo_children():
                    if isinstance(w, (tk.Scale, ctk.CTkSlider)):
                        w.destroy()
                spot_slider(self.sidebar, spot, self.generate_selected_chart)


def generate_chart_group(self):
    from state.app_state import get_state_value
    from utils.time import time_to_expiration
    
    successful = 0
    skipped = 0
    failed = []
    # Track chart windows so we can bring them to front after dialog
    self._chart_windows = []
    # Track which ticker/expiration pairs have been generated to prevent duplicates
    generated_pairs = set()
    # Set flag to prevent spot slider from triggering chart regeneration during group generation
    self._generating_chart_group = True
    
    # Load group settings
    group_settings = get_state_value("group_settings", {})
    
    # Load chart group mode (default to "Build All")
    chart_group_mode = get_state_value("chart_group_mode", "Build All")
    
    # Get existing chart windows if in "Build Missing Dates Only" mode
    existing_charts = set()
    if chart_group_mode == "Build Missing Dates Only":
        # Collect all existing chart windows and extract their ticker/expiration pairs
        all_chart_windows = []
        
        # Collect tracked windows
        if hasattr(self, '_chart_windows') and self._chart_windows:
            for win in self._chart_windows:
                try:
                    if win.winfo_exists():
                        all_chart_windows.append(win)
                except:
                    pass
        
        # Collect untracked chart windows
        try:
            for child in self.root.winfo_children():
                if isinstance(child, ctk.CTkToplevel):
                    try:
                        if child.winfo_exists():
                            title = child.title()
                            if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                                all_chart_windows.append(child)
                    except:
                        pass
        except:
            pass
        
        # Extract ticker and expiration from window titles
        # Format: "SYMBOL Model Exposure - DATE | TIME" or "SYMBOL Heston Model Analysis - DATE | TIME"
        for win in all_chart_windows:
            try:
                if win.winfo_exists():
                    title = win.title()
                    # Parse title to extract symbol and date
                    # Titles typically have format: "SYMBOL ... - DATE | TIME"
                    if " - " in title:
                        parts = title.split(" - ")
                        if len(parts) >= 2:
                            symbol_part = parts[0].split()[0]  # First word is symbol
                            date_part = parts[1].split(" |")[0].strip()  # Date before "|"
                            # Create a key for this chart
                            existing_charts.add((symbol_part, date_part))
            except:
                pass
    
    for symbol, ui in self.ticker_tabs.items():
        if symbol not in self.ticker_data:
            skipped += 1
            continue
        
        # Get settings for this ticker (default to include=True, range="1 day")
        ticker_settings = group_settings.get(symbol, {"include": True, "range": "1 day"})
        
        # Check if ticker is included - skip if checkbox is unchecked
        if not ticker_settings.get("include", True):
            skipped += 1
            continue
        
        # Get range setting
        range_str = ticker_settings.get("range", "1 day")
        # Parse range (e.g., "2 days" -> 2)
        try:
            num_days = int(range_str.split()[0])
        except:
            num_days = 1
        
        # Get state and available expirations
        state = self.ticker_data[symbol]
        if not state or not state.exp_data_map:
            skipped += 1
            continue
        
        # Get sorted expiration dates
        expirations = sorted(state.exp_data_map.keys())
        if not expirations:
            skipped += 1
            continue
        
        # Limit to the number of days specified
        expirations_to_use = expirations[:num_days]
        
        # Generate charts for each expiration in the range
        for exp in expirations_to_use:
            # Create a unique key for this ticker/expiration pair
            pair_key = (symbol, exp)
            if pair_key in generated_pairs:
                # Skip if we've already generated this pair
                continue
            
            # In "Build Missing Dates Only" mode, check if chart already exists
            if chart_group_mode == "Build Missing Dates Only":
                # Extract date from expiration string (format: "YYYY-MM-DD:...")
                exp_date = exp.split(":")[0] if ":" in exp else exp
                chart_key = (symbol, exp_date)
                if chart_key in existing_charts:
                    # Chart already exists, skip it
                    skipped += 1
                    continue
            
            if exp not in state.exp_data_map or state.exp_data_map[exp].empty:
                continue
            
            # Try to generate chart
            try:
                # Select the tab for this ticker
                self.notebook.select(ui["tab"])
                
                # Validate data using the same logic as generate_selected_chart
                spot = state.price
                if spot <= 0:
                    failed.append(f"{symbol} (invalid spot price)")
                    continue
                
                T = time_to_expiration(exp)
                if T <= 0:
                    failed.append(f"{symbol} (invalid expiration)")
                    continue
                
                df = state.exp_data_map[exp]
                has_valid_data = False
                # Use itertuples() instead of iterrows() for better performance
                for row in df.itertuples(index=False):
                    try:
                        K = float(row.Strike) if hasattr(row, 'Strike') else 0
                        if pd.isna(K) or K <= 0:
                            continue
                        for opt in ("CALL", "PUT"):
                            # Column names are IV_Call, OI_Call, IV_Put, OI_Put (capital C/P)
                            opt_key = opt.capitalize()  # "CALL" -> "Call", "PUT" -> "Put"
                            iv_attr = f"IV_{opt_key}"
                            oi_attr = f"OI_{opt_key}"
                            iv_val = getattr(row, iv_attr, 0)
                            oi_val = getattr(row, oi_attr, 0)
                            # Handle NaN, None, or empty values
                            iv = 0.0 if (pd.isna(iv_val) or iv_val == "" or iv_val is None) else float(iv_val)
                            oi = 0.0 if (pd.isna(oi_val) or oi_val == "" or oi_val is None) else float(oi_val)
                            if iv > 0 and oi > 0:
                                has_valid_data = True
                                break
                        if has_valid_data:
                            break
                    except (ValueError, TypeError, AttributeError):
                        continue
                
                if has_valid_data:
                    # Mark this pair as generated BEFORE calling generate_selected_chart
                    # to prevent infinite loops if the function triggers itself
                    generated_pairs.add(pair_key)
                    # Temporarily set the expiration in the UI for this ticker
                    original_exp = ui["exp_var"].get()
                    ui["exp_var"].set(exp)
                    # Generate the chart
                    generate_selected_chart(self)
                    # Restore original expiration
                    ui["exp_var"].set(original_exp)
                    successful += 1
                else:
                    if symbol not in [f.split()[0] if isinstance(f, str) and " " in f else f for f in failed]:
                        failed.append(symbol)
            except Exception as e:
                failed.append(f"{symbol} (error: {str(e)})")
    
    # Show summary using timed message (non-modal, auto-closes)
    # Show it AFTER a brief delay to ensure chart windows are fully rendered
    if successful > 0:
        msg = f"Generated {successful} chart(s)"
        if skipped > 0:
            msg += f"\nSkipped {skipped} ticker(s) (no data or expiration)"
        if failed:
            msg += f"\nFailed: {', '.join(failed)}"
        # Delay showing dialog slightly and ensure chart windows stay in front
        def show_dialog_and_keep_charts_front():
            # Bring all chart windows to front before showing dialog
            if hasattr(self, '_chart_windows') and self._chart_windows:
                for win in self._chart_windows:
                    try:
                        if win.winfo_exists():
                            win.lift()
                            win.focus()
                    except:
                        pass
                self.root.update_idletasks()
            # Show timed message (non-modal, won't steal focus, not transient to root)
            dialogs.show_timed_message(self.root, "Chart Group Complete", msg, duration_ms=3000)
            # Bring chart windows to front after dialog appears
            def keep_charts_front():
                if hasattr(self, '_chart_windows') and self._chart_windows:
                    for win in self._chart_windows:
                        try:
                            if win.winfo_exists():
                                win.lift()
                                win.focus()
                        except:
                            pass
            self.root.after(100, keep_charts_front)
            
            # Update clear graphs button state after charts are created
            if hasattr(self, 'update_clear_graphs_button_state'):
                self.update_clear_graphs_button_state()
            
            # Update focus bar after charts are created
            if hasattr(self, 'update_focus_bar'):
                self.update_focus_bar()
            
            # After dialog closes, remove transient so main window can come forward when clicked
            def remove_transient_after_dialog():
                if hasattr(self, '_chart_windows') and self._chart_windows:
                    for win in self._chart_windows:
                        try:
                            if win.winfo_exists():
                                # Remove transient by setting it to None (makes window independent)
                                # Note: In Tkinter, you can't truly "remove" transient, but we can
                                # make the window independent by not having it transient to anything
                                # The window will still exist but won't be forced above main window
                                pass  # We'll handle this differently - just ensure they're lifted
                        except:
                            pass
            # Remove transient relationship after dialog closes (3000ms + buffer)
            self.root.after(3200, remove_transient_after_dialog)
        self.root.after(200, show_dialog_and_keep_charts_front)
    elif failed:
        dialogs.warning(
            "No Charts Generated",
            f"Could not generate charts for any tickers.\n"
            f"Failed: {', '.join(failed)}\n"
            f"Skipped: {skipped} ticker(s)"
        )
    else:
        dialogs.warning(
            "No Charts Generated",
            f"No valid data found for any tickers.\n"
            f"Please ensure:\n"
            f"- Data has been fetched\n"
            f"- Expiration dates are selected\n"
            f"- Options have IV and Open Interest data"
        )
    
    # Clean up tracking
    if hasattr(self, '_chart_windows'):
        delattr(self, '_chart_windows')
    # Clear the group generation flag
    if hasattr(self, '_generating_chart_group'):
        self._generating_chart_group = False

def _bring_chart_windows_to_front(self):
    """Bring all chart windows to the front"""
    if hasattr(self, '_chart_windows'):
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    win.lift()
                    win.focus()
            except:
                pass

def close_all_chart_windows(self):
    """Close all active chart windows and clean up the tracking list"""
    if hasattr(self, '_chart_windows'):
        # Close all windows that still exist
        for win in self._chart_windows[:]:  # Use slice copy to avoid modification during iteration
            try:
                if win.winfo_exists():
                    win.destroy()
            except:
                pass
        # Clear the list
        self._chart_windows.clear()
    
    # Also check for any other chart windows (like Heston charts) by checking root's children
    # Find all CTkToplevel windows that look like chart windows
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                # Check if it's a chart window by title patterns
                title = child.title()
                if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                    try:
                        if child.winfo_exists():
                            child.destroy()
                    except:
                        pass
    except:
        pass
    
    # Update button state after closing
    update_clear_graphs_button_state(self)
    
    # Update focus bar after closing charts
    if hasattr(self, 'update_focus_bar'):
        self.update_focus_bar()

def has_active_chart_windows(self):
    """Check if there are any active chart windows"""
    # Check tracked windows
    if hasattr(self, '_chart_windows') and self._chart_windows:
        # Clean up dead windows first
        active_windows = []
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    active_windows.append(win)
            except:
                pass
        self._chart_windows[:] = active_windows
        if active_windows:
            return True
    
    # Also check for untracked chart windows (like Heston charts)
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                title = child.title()
                if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                    try:
                        if child.winfo_exists():
                            return True
                    except:
                        pass
    except:
        pass
    
    return False

def update_clear_graphs_button_state(self):
    """Update the state of the clear graphs button based on active chart windows"""
    if hasattr(self, 'clear_graphs_button'):
        if has_active_chart_windows(self):
            self.clear_graphs_button.configure(state="normal")
        else:
            self.clear_graphs_button.configure(state="disabled")  # Window may have been closed

def get_tickers_with_charts(self):
    """Get a set of ticker symbols that have at least one active chart window"""
    tickers = set()
    
    # Check tracked windows
    if hasattr(self, '_chart_windows') and self._chart_windows:
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    title = win.title()
                    # Extract ticker from title (format: "SYMBOL Model Exposure - DATE | TIME" or "SYMBOL Heston Model Analysis - DATE | TIME")
                    # Titles typically start with the ticker symbol
                    parts = title.split()
                    if parts:
                        ticker = parts[0]
                        # Validate it looks like a ticker (uppercase, alphanumeric, 1-5 chars)
                        if ticker.isalnum() and ticker.isupper() and 1 <= len(ticker) <= 5:
                            tickers.add(ticker)
            except:
                pass
    
    # Also check untracked chart windows (like Heston charts)
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                try:
                    if child.winfo_exists():
                        title = child.title()
                        if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                            # Extract ticker from title
                            parts = title.split()
                            if parts:
                                ticker = parts[0]
                                if ticker.isalnum() and ticker.isupper() and 1 <= len(ticker) <= 5:
                                    tickers.add(ticker)
                except:
                    pass
    except:
        pass
    
    return tickers

def focus_ticker_charts(self, symbol):
    """Bring all charts for a specific ticker to front, move others to back"""
    # First, move all chart windows to back
    all_chart_windows = []
    
    # Collect tracked windows
    if hasattr(self, '_chart_windows') and self._chart_windows:
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    all_chart_windows.append(win)
            except:
                pass
    
    # Collect untracked chart windows
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                try:
                    if child.winfo_exists():
                        title = child.title()
                        if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                            all_chart_windows.append(child)
                except:
                    pass
    except:
        pass
    
    # Separate windows by ticker
    target_windows = []
    other_windows = []
    
    for win in all_chart_windows:
        try:
            if win.winfo_exists():
                title = win.title()
                # Check if this window is for the target ticker
                if title.startswith(symbol + " ") or title.startswith(symbol + "-"):
                    target_windows.append(win)
                else:
                    other_windows.append(win)
        except:
            pass
    
    # Move other windows to back first
    for win in other_windows:
        try:
            if win.winfo_exists():
                win.lower()
        except:
            pass
    
    # Bring target ticker's windows to front
    for win in target_windows:
        try:
            if win.winfo_exists():
                win.lift()
                win.focus()
        except:
            pass
    
    # Update focus bar after focusing
    if hasattr(self, 'update_focus_bar'):
        self.update_focus_bar()

def close_ticker_charts(self, symbol):
    """Close all chart windows for a specific ticker symbol"""
    closed_count = 0
    
    # Collect all chart windows
    all_chart_windows = []
    
    # Collect tracked windows
    if hasattr(self, '_chart_windows') and self._chart_windows:
        for win in self._chart_windows[:]:  # Use slice copy
            try:
                if win.winfo_exists():
                    all_chart_windows.append(win)
            except:
                pass
    
    # Collect untracked chart windows
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                try:
                    if child.winfo_exists():
                        title = child.title()
                        if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                            all_chart_windows.append(child)
                except:
                    pass
    except:
        pass
    
    # Close windows for the target ticker
    for win in all_chart_windows:
        try:
            if win.winfo_exists():
                title = win.title()
                # Check if this window is for the target ticker
                if title.startswith(symbol + " ") or title.startswith(symbol + "-"):
                    win.destroy()
                    closed_count += 1
                    # Remove from tracked list if it was there
                    if hasattr(self, '_chart_windows') and win in self._chart_windows:
                        self._chart_windows.remove(win)
        except:
            pass
    
    # Update button states after closing
    update_clear_graphs_button_state(self)
    
    # Update focus bar after closing
    if hasattr(self, 'update_focus_bar'):
        self.update_focus_bar()
    
    return closed_count

def get_ticker_chart_windows(self, symbol):
    """Get all chart windows for a specific ticker and extract expiration dates"""
    chart_info = []  # List of (window, expiration_date) tuples
    
    # Collect all chart windows
    all_chart_windows = []
    
    # Collect tracked windows
    if hasattr(self, '_chart_windows') and self._chart_windows:
        for win in self._chart_windows:
            try:
                if win.winfo_exists():
                    all_chart_windows.append(win)
            except:
                pass
    
    # Collect untracked chart windows
    try:
        for child in self.root.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                try:
                    if child.winfo_exists():
                        title = child.title()
                        if any(keyword in title for keyword in ["Exposure", "Heston", "Analysis", "Chart"]):
                            all_chart_windows.append(child)
                except:
                    pass
    except:
        pass
    
    # Extract windows and expiration dates for the target ticker
    for win in all_chart_windows:
        try:
            if win.winfo_exists():
                title = win.title()
                # Check if this window is for the target ticker
                if title.startswith(symbol + " ") or title.startswith(symbol + "-"):
                    # Extract expiration date from title
                    # Format: "SYMBOL Model Exposure - DATE | TIME" or "SYMBOL Heston Model Analysis - DATE | TIME"
                    exp_date = None
                    if " - " in title:
                        parts = title.split(" - ")
                        if len(parts) >= 2:
                            date_part = parts[1].split(" |")[0].strip()  # Date before "|"
                            exp_date = date_part
                    chart_info.append((win, exp_date))
        except:
            pass
    
    return chart_info

def regenerate_chart_data(self, symbol, exp):
    """Regenerate chart data for a specific symbol and expiration"""
    from utils.time import time_to_expiration
    
    # Get ticker state
    if symbol not in self.ticker_data:
        return None
    
    state = self.ticker_data[symbol]
    if not state or exp not in state.exp_data_map:
        return None
    
    # Get expiration data
    df = state.exp_data_map[exp]
    if df is None or df.empty:
        return None
    
    spot = state.price
    if spot <= 0:
        return None
    
    T = time_to_expiration(exp)
    if T <= 0:
        return None
    
    model_name = self.model_var.get()
    CONTRACT_MULT = 100
    rows = []
    
    # Generate exposure data
    for row in df.itertuples(index=False):
        K = float(row.Strike) if hasattr(row, 'Strike') else 0
        if K <= 0:
            continue

        for opt in ("CALL", "PUT"):
            opt_key = opt.capitalize()
            iv_attr = f"IV_{opt_key}"
            oi_attr = f"OI_{opt_key}"
            iv = float(getattr(row, iv_attr, 0) or 0)
            oi = float(getattr(row, oi_attr, 0) or 0)
            if iv <= 0 or oi <= 0:
                continue

            sign = 1 if opt == "CALL" else -1

            if model_name == "Gamma":
                g = gamma(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * CONTRACT_MULT * (spot ** 2) * 0.01
                exp_val = sign * g * scale
            elif model_name == "Vanna":
                v = vanna(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * CONTRACT_MULT * spot * iv
                exp_val = sign * abs(v) * scale
            elif model_name == "Volga":
                vg = volga(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                ve = vega(spot, K, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv)
                scale = oi * ve
                exp_val = sign * abs(vg) * scale
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
        return None

    df_plot = build_exposure_dataframe(rows)
    total = df_plot["Exposure"].sum() / 1e9

    zero_gamma = find_zero_gamma(
        state.exp_data_map[exp],
        spot * 0.9,
        spot * 1.1,
        60,
        T,
        RISK_FREE_RATE,
        DIVIDEND_YIELD
    )
    
    return {
        "df_plot": df_plot,
        "symbol": symbol,
        "exp_date": exp.split(":")[0],
        "model_name": model_name,
        "total": total,
        "zero_gamma": zero_gamma
    }

def merge_ticker_charts_to_new_window(self, symbol):
    """Merge all charts for a ticker into a new tabbed window"""
    # Get all chart windows for this ticker
    chart_windows = get_ticker_chart_windows(self, symbol)
    
    if not chart_windows:
        dialogs.warning("No Charts", f"No active charts found for {symbol}")
        return
    
    # Extract expiration dates from window titles
    expiration_dates = []
    for win, exp_date in chart_windows:
        if exp_date:
            expiration_dates.append(exp_date)
    
    # Remove duplicates and sort
    expiration_dates = sorted(set(expiration_dates))
    
    if not expiration_dates:
        dialogs.warning("No Expiration Data", f"Could not extract expiration dates from charts for {symbol}")
        return
    
    # Map expiration dates back to full expiration strings (from ticker_data)
    if symbol not in self.ticker_data:
        dialogs.warning("No Data", f"No data available for {symbol}")
        return
    
    state = self.ticker_data[symbol]
    if not state or not state.exp_data_map:
        dialogs.warning("No Data", f"No expiration data available for {symbol}")
        return
    
    # Build mapping from date to full expiration string
    # Handle both exact matches and date-only matches
    date_to_exp = {}
    for exp in state.exp_data_map.keys():
        exp_date = exp.split(":")[0] if ":" in exp else exp
        # Store both the date and the full expiration string
        if exp_date not in date_to_exp:
            date_to_exp[exp_date] = []
        date_to_exp[exp_date].append(exp)
    
    # Match expiration dates to full expiration strings
    matched_expirations = []
    for exp_date in expiration_dates:
        if exp_date in date_to_exp:
            # Use the first matching expiration (typically there's only one per date)
            matched_expirations.extend(date_to_exp[exp_date])
        else:
            # Try to match by date format (in case of slight variations)
            for exp_key in state.exp_data_map.keys():
                key_date = exp_key.split(":")[0] if ":" in exp_key else exp_key
                if key_date == exp_date or exp_date in key_date or key_date in exp_date:
                    if exp_key not in matched_expirations:
                        matched_expirations.append(exp_key)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_expirations = []
    for exp in matched_expirations:
        if exp not in seen:
            seen.add(exp)
            unique_expirations.append(exp)
    matched_expirations = unique_expirations
    
    if not matched_expirations:
        dialogs.warning("No Matches", f"Could not match expiration dates to data for {symbol}")
        return
    
    # Close existing windows for this ticker
    close_ticker_charts(self, symbol)
    
    # Create new merged window with tabs
    merged_win = ctk.CTkToplevel(self.root)
    merged_win.geometry("1000x750")
    model_name = self.model_var.get()
    current_time = datetime.datetime.now().strftime('%I:%M %p')
    merged_win.title(f"{symbol} {model_name} Exposure - Merged | {current_time}")
    
    # Create notebook for organizing charts by expiration (using ttk.Notebook)
    # Use a regular tk.Frame container for the notebook to ensure proper styling
    container = tk.Frame(merged_win)
    container.pack(fill="both", expand=True, padx=10, pady=10)
    
    notebook = ttk.Notebook(container)
    notebook.pack(fill="both", expand=True)
    
    # Sort expirations chronologically by date (parse and sort properly)
    def parse_expiration_date(exp):
        """Extract date from expiration string for sorting"""
        try:
            date_str = exp.split(":")[0] if ":" in exp else exp
            # Parse as YYYY-MM-DD
            parts = date_str.split("-")
            if len(parts) == 3:
                year, month, day = map(int, parts)
                return (year, month, day)
        except:
            pass
        return (0, 0, 0)  # Fallback for invalid dates
    
    sorted_expirations = sorted(matched_expirations, key=parse_expiration_date)
    
    # Create a tab for each expiration and regenerate the chart
    tabs_created = 0
    for exp in sorted_expirations:
        exp_date = exp.split(":")[0] if ":" in exp else exp
        
        # Regenerate chart data for this expiration
        chart_data = regenerate_chart_data(self, symbol, exp)
        
        if not chart_data:
            # Skip this expiration if chart data couldn't be regenerated
            continue
        
        # Create tab frame
        tab = tk.Frame(notebook)
        notebook.add(tab, text=exp_date)
        
        # Embed chart in this tab
        try:
            # Create a container frame in the tab for the chart
            chart_container = tk.Frame(tab)
            chart_container.pack(fill="both", expand=True)
            
            embed_matplotlib_chart(
                chart_container,
                chart_data["df_plot"],
                chart_data["symbol"],
                chart_data["exp_date"],
                chart_data["model_name"],
                chart_data["total"],
                chart_data["zero_gamma"]
            )
            tabs_created += 1
        except Exception as e:
            # If chart embedding fails, add error message to tab
            import traceback
            error_label = tk.Label(
                tab,
                text=f"Error loading chart for {exp_date}:\n{str(e)}",
                fg="red",
                justify="left",
                wraplength=800
            )
            error_label.pack(pady=20)
            print(f"Error embedding chart for {exp_date}: {traceback.format_exc()}")
    
    # If no tabs were created, show error and close window
    if tabs_created == 0:
        merged_win.destroy()
        dialogs.error(
            "Merge Failed",
            f"Could not regenerate charts for {symbol}.\n"
            "Make sure data is still available for this ticker."
        )
        return
    
    # Track the merged window in chart windows list
    if not hasattr(self, '_chart_windows'):
        self._chart_windows = []
    self._chart_windows.append(merged_win)
    
    # Update focus bar and button states
    if hasattr(self, 'update_clear_graphs_button_state'):
        self.update_clear_graphs_button_state()
    if hasattr(self, 'update_focus_bar'):
        self.update_focus_bar()
    
    # Bring window to front
    merged_win.update_idletasks()
    merged_win.lift()
    merged_win.focus()
