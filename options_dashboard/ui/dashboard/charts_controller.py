import customtkinter as ctk
import datetime
import tkinter as tk
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
        if symbol not in self.ticker_data:
            dialogs.warning("No Data", "Please fetch data first.")
            return
        
        state = self.ticker_data[symbol]
        # Single view entries use the key format "_single_{symbol}"
        single_view_key = f"_single_{symbol}"
        ui = self.ticker_tabs.get(single_view_key)
        if not ui:
            dialogs.warning("No Data", "Please fetch data first.")
            return
        
        exp = ui["exp_var"].get()
        if not exp:
            dialogs.warning("No Expiration", "Please select an expiration date.")
            return
        
        # Create chart key - use symbol and exp only to catch duplicate button clicks
        # (spot_override will be None for button clicks, so we can use a simpler key)
        chart_key = (symbol, exp, spot_override if spot_override is not None else state.price)
        
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
    for _, row in state.exp_data_map[exp].iterrows():
        K = float(row["Strike"])
        if K <= 0:
            continue

        for opt in ("CALL", "PUT"):
            # Column names are IV_Call, OI_Call, IV_Put, OI_Put (capital C/P)
            opt_key = opt.capitalize()  # "CALL" -> "Call", "PUT" -> "Put"
            iv = float(row.get(f"IV_{opt_key}", 0) or 0)
            oi = float(row.get(f"OI_{opt_key}", 0) or 0)
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
                for _, row in df.iterrows():
                    try:
                        K = float(row.get("Strike", 0) or 0)
                        if pd.isna(K) or K <= 0:
                            continue
                        for opt in ("CALL", "PUT"):
                            # Column names are IV_Call, OI_Call, IV_Put, OI_Put (capital C/P)
                            opt_key = opt.capitalize()  # "CALL" -> "Call", "PUT" -> "Put"
                            iv_val = row.get(f"IV_{opt_key}", 0)
                            oi_val = row.get(f"OI_{opt_key}", 0)
                            # Handle NaN, None, or empty values
                            iv = 0.0 if (pd.isna(iv_val) or iv_val == "" or iv_val is None) else float(iv_val)
                            oi = 0.0 if (pd.isna(oi_val) or oi_val == "" or oi_val is None) else float(oi_val)
                            if iv > 0 and oi > 0:
                                has_valid_data = True
                                break
                        if has_valid_data:
                            break
                    except (ValueError, TypeError):
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
                pass  # Window may have been closed
