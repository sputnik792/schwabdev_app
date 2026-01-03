import customtkinter as ctk
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
        win.title(f"{symbol} {model_name} Exposure - {exp_date}")
        # Make window appear in front and stay above main window (but not always on top of everything)
        win.transient(self.root)  # Makes it stay above main window
        win.lift()
        win.focus()
        # Store window reference if we're in a group generation context
        if hasattr(self, '_chart_windows'):
            self._chart_windows.append(win)
        embed_matplotlib_chart(
            win,
            df_plot,
            symbol,
            exp_date,
            model_name,
            total,
            zero_gamma
        )

    # Spot slider
    for w in self.sidebar.winfo_children():
        if isinstance(w, (tk.Scale, ctk.CTkSlider)):
            w.destroy()

    spot_slider(self.sidebar, spot, self.generate_selected_chart)


def generate_chart_group(self):
    successful = 0
    skipped = 0
    failed = []
    # Track chart windows so we can bring them to front after dialog
    self._chart_windows = []
    
    for symbol, ui in self.ticker_tabs.items():
        if symbol not in self.ticker_data:
            skipped += 1
            continue
        
        # Check if expiration is selected
        exp = ui["exp_var"].get()
        if not exp:
            skipped += 1
            continue
        
        # Check if expiration has data
        state = self.ticker_data[symbol]
        if exp not in state.exp_data_map or state.exp_data_map[exp].empty:
            skipped += 1
            continue
        
        # Try to generate chart
        self.notebook.select(ui["tab"])
        try:
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
                # Generate the chart
                generate_selected_chart(self)
                successful += 1
            else:
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
        # Delay showing dialog slightly and ensure chart windows stay above main window
        def show_dialog_and_keep_charts_front():
            # Bring chart windows to front before showing dialog
            if hasattr(self, '_chart_windows') and self._chart_windows:
                self._bring_chart_windows_to_front()
                self.root.update_idletasks()
            # Show timed message (non-modal, won't steal focus)
            dialogs.show_timed_message(self.root, "Chart Group Complete", msg, duration_ms=3000)
            # Bring chart windows back to front after dialog appears
            self.root.after(100, lambda: self._bring_chart_windows_to_front() if hasattr(self, '_chart_windows') else None)
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
