import threading
import datetime
from tkinter import filedialog

from state.ticker_state import TickerState
from data.schwab_api import fetch_stock_price, fetch_option_chain
from data.csv_loader import load_csv_index
from data.ticker_history import record_ticker_search
from ui import dialogs
from ui.dashboard.tabs import highlight_rows_by_strike, format_row_data
from models.greeks import calculate_prob_itm
from utils.time import time_to_expiration
from config import RISK_FREE_RATE
from tksheet import Sheet

def fetch_worker(self, symbol):
    try:
        price = fetch_stock_price(self.client, symbol)
        exp_map, expirations = fetch_option_chain(self.client, symbol)

        # Calculate Prob ITM for each expiration
        for exp_date in expirations:
            df = exp_map.get(exp_date)
            if df is not None and not df.empty:
                T = time_to_expiration(exp_date)
                exp_map[exp_date] = calculate_prob_itm(df, price, T, RISK_FREE_RATE)

        state = TickerState(
            symbol=symbol,
            price=price,
            exp_data_map=exp_map,
            last_updated=datetime.datetime.now()
        )

        def update_ui():
            # Multi-view should always fetch and store its own data for preset tickers
            # But we need to preserve single-view data if it exists
            # Check if there's existing single-view data and back it up
            existing_state = self.ticker_data.get(symbol)
            if existing_state and hasattr(existing_state, '_from_single_view') and existing_state._from_single_view:
                # Backup single-view data before overwriting
                if not hasattr(self, 'single_view_data_backup'):
                    self.single_view_data_backup = {}
                self.single_view_data_backup[symbol] = existing_state
                print(f"[MULTI VIEW] Backed up single-view data for {symbol} before overwriting")
            
            # Store multi-view data (without _from_single_view flag, or explicitly mark as multi-view)
            state._from_single_view = False  # Explicitly mark as multi-view data
            self.ticker_data[symbol] = state
            # Also update backup if it exists (in case it was backed up before)
            if hasattr(self, 'multi_view_data_backup'):
                self.multi_view_data_backup[symbol] = state
            ui = self.ticker_tabs.get(symbol)
            if not ui:
                return

            ui["price_var"].set(f"${price:.2f}" if price else "—")

            if expirations:
                ui["exp_dropdown"].configure(values=expirations)
                ui["exp_var"].set(expirations[0])
                self.update_table_for_symbol(symbol, expirations[0])
            
            # Mark this symbol as completed
            if hasattr(self, 'fetching_symbols') and hasattr(self, 'completed_symbols'):
                self.completed_symbols.add(symbol)
                
                # Check if all symbols are done
                if self.completed_symbols == self.fetching_symbols:
                    # Close fetching dialog if it exists
                    if hasattr(self, 'fetching_dialog'):
                        try:
                            self.fetching_dialog.destroy()
                            delattr(self, 'fetching_dialog')
                        except:
                            pass
                    
                    # All done! Show the completion message
                    dialogs.show_timed_message(
                        self.root,
                        "Fetch Complete",
                        f"All {len(self.fetching_symbols)} tickers loaded successfully!",
                        3000
                    )
                    # Enable Generate Chart Group button if it exists
                    if hasattr(self, 'generate_chart_group_button'):
                        self.generate_chart_group_button.configure(state="normal")
                    # Reset tracking for next fetch
                    self.fetching_symbols.clear()
                    self.completed_symbols.clear()

        self.root.after(0, update_ui)

    except RuntimeError as e:
        if str(e) == "AUTH_REQUIRED":
            def handle_error():
                dialogs.error(
                    "Authentication Required",
                    "Schwab authentication expired.\nPlease reconnect."
                )
        # Mark as completed even on error so we don't wait forever
        if hasattr(self, 'fetching_symbols') and hasattr(self, 'completed_symbols'):
            self.completed_symbols.add(symbol)
            if self.completed_symbols == self.fetching_symbols:
                # Close fetching dialog if it exists
                if hasattr(self, 'fetching_dialog'):
                    try:
                        self.fetching_dialog.destroy()
                        delattr(self, 'fetching_dialog')
                    except:
                        pass
                self.fetching_symbols.clear()
                self.completed_symbols.clear()
            self.root.after(0, handle_error)
    except Exception as e:
        def handle_error():
            dialogs.error("Error", f"{symbol}: {e}")
            # Mark as completed even on error so we don't wait forever
            if hasattr(self, 'fetching_symbols') and hasattr(self, 'completed_symbols'):
                self.completed_symbols.add(symbol)
                if self.completed_symbols == self.fetching_symbols:
                    # Close fetching dialog if it exists
                    if hasattr(self, 'fetching_dialog'):
                        try:
                            self.fetching_dialog.destroy()
                            delattr(self, 'fetching_dialog')
                        except:
                            pass
                    self.fetching_symbols.clear()
                    self.completed_symbols.clear()
        self.root.after(0, handle_error)

def fetch_single_symbol(dashboard, symbol):
    symbol = symbol.strip().upper()
    if not symbol:
        return

    def worker():
        try:
            price = fetch_stock_price(dashboard.client, symbol)
            exp_map, expirations = fetch_option_chain(dashboard.client, symbol)

            # Calculate Prob ITM for each expiration
            for exp_date in expirations:
                df = exp_map.get(exp_date)
                if df is not None and not df.empty:
                    T = time_to_expiration(exp_date)
                    exp_map[exp_date] = calculate_prob_itm(df, price, T, RISK_FREE_RATE)

            state = TickerState(
                symbol=symbol,
                price=price,
                exp_data_map=exp_map,
                last_updated=datetime.datetime.now()
            )

            def update():
                dashboard.ticker_data[symbol] = state

                if symbol not in dashboard.ticker_tabs:
                    dashboard.preset_tickers.append(symbol)
                    dashboard.rebuild_tabs()

                ui = dashboard.ticker_tabs[symbol]
                ui["price_var"].set(f"${price:.2f}")
                ui["exp_dropdown"].configure(values=expirations)
                ui["exp_var"].set(expirations[0])

                dashboard.update_table_for_symbol(symbol, expirations[0])

            dashboard.root.after(0, update)

        except Exception as e:
            dashboard.root.after(
                0, lambda: dialogs.error("Fetch Error", str(e))
            )

    threading.Thread(target=worker, daemon=True).start()

def fetch_single_symbol_for_view(dashboard, symbol, ticker_var, price_var, exp_var, exp_dropdown, ticker_label):
    """Fetch data for a single ticker in the single view"""
    symbol = symbol.strip().upper()
    if not symbol:
        dialogs.warning("Invalid Ticker", "Please enter a ticker symbol.")
        return

    def worker():
        try:
            price = fetch_stock_price(dashboard.client, symbol)
            exp_map, expirations = fetch_option_chain(dashboard.client, symbol)

            # Calculate Prob ITM for each expiration
            for exp_date in expirations:
                df = exp_map.get(exp_date)
                if df is not None and not df.empty:
                    T = time_to_expiration(exp_date)
                    exp_map[exp_date] = calculate_prob_itm(df, price, T, RISK_FREE_RATE)

            state = TickerState(
                symbol=symbol,
                price=price,
                exp_data_map=exp_map,
                last_updated=datetime.datetime.now()
            )

            def update():
                # Store data with a flag to indicate it's from single view
                # But first, preserve multi-view data if it exists
                existing_state = dashboard.ticker_data.get(symbol)
                if existing_state and (not hasattr(existing_state, '_from_single_view') or not existing_state._from_single_view):
                    # Backup multi-view data before overwriting
                    if not hasattr(dashboard, 'multi_view_data_backup'):
                        dashboard.multi_view_data_backup = {}
                    dashboard.multi_view_data_backup[symbol] = existing_state
                    print(f"[SINGLE VIEW] Backed up multi-view data for {symbol} before overwriting")
                
                state._from_single_view = True
                dashboard.ticker_data[symbol] = state
                # Also update backup if it exists (in case it was backed up before)
                if hasattr(dashboard, 'single_view_data_backup'):
                    dashboard.single_view_data_backup[symbol] = state
                print(f"[SINGLE VIEW SAVE] ========== SAVING DATA ==========")
                print(f"[SINGLE VIEW SAVE] Symbol: {symbol}")
                print(f"[SINGLE VIEW SAVE] Set _from_single_view = True on state object")
                print(f"[SINGLE VIEW SAVE] Stored in ticker_data[{symbol}]")
                print(f"[SINGLE VIEW SAVE] Verifying flag after save: hasattr={hasattr(state, '_from_single_view')}, value={getattr(state, '_from_single_view', 'NOT SET')}")
                print(f"[SINGLE VIEW SAVE] Price: {state.price}")
                print(f"[SINGLE VIEW SAVE] Expirations: {list(state.exp_data_map.keys()) if state.exp_data_map else 'None'}")
                print(f"[SINGLE VIEW SAVE] All ticker_data keys: {list(dashboard.ticker_data.keys())}")
                # Verify the stored state also has the flag
                stored_state = dashboard.ticker_data.get(symbol)
                if stored_state:
                    print(f"[SINGLE VIEW SAVE] Stored state has flag: hasattr={hasattr(stored_state, '_from_single_view')}, value={getattr(stored_state, '_from_single_view', 'NOT SET')}")
                print(f"[SINGLE VIEW SAVE] ==================================")
                
                try:
                    # Update ticker input (but not display until fetch succeeds)
                    ticker_var.set(symbol)
                    # Don't update display label here - it will be updated after successful fetch
                    
                    # Update price - ONLY update single view's price_var
                    price_var.set(f"${price:.2f}" if price else "—")
                    print(f"[SINGLE VIEW SAVE] Updated price_var")
                    
                    # Get the single view UI components - these are independent from multi-view
                    # First, try to get sheet from stored single view components
                    sheet = None
                    cols = None
                    
                    # Look for any single view entry to get the sheet widget (it's the same sheet for all symbols)
                    # Single view entries use the key format "_single_{symbol}" or "_SINGLE_VIEW_PLACEHOLDER"
                    single_view_ui = None
                    # First try to find the placeholder entry (created in layout.py)
                    if "_SINGLE_VIEW_PLACEHOLDER" in dashboard.ticker_tabs:
                        placeholder_ui = dashboard.ticker_tabs["_SINGLE_VIEW_PLACEHOLDER"]
                        if placeholder_ui.get("_is_single_view") or "ticker_var" in placeholder_ui:
                            single_view_ui = placeholder_ui
                            sheet = placeholder_ui.get("sheet")
                            cols = placeholder_ui.get("cols")
                    
                    # If not found, look for any other single view entry
                    if not sheet:
                        for existing_key, existing_ui in dashboard.ticker_tabs.items():
                            if existing_key.startswith("_single_") and (existing_ui.get("_is_single_view") or "ticker_var" in existing_ui):
                                single_view_ui = existing_ui
                                sheet = existing_ui.get("sheet")
                                cols = existing_ui.get("cols")
                                if sheet:  # Found sheet, break
                                    break
                    
                    # If still not found, get sheet from single view structure
                    if not sheet and hasattr(dashboard, 'single_view') and dashboard.single_view:
                        def find_sheet_recursive(widget):
                            try:
                                for child in widget.winfo_children():
                                    if isinstance(child, Sheet):
                                        return child, child.headers()
                                    if hasattr(child, 'winfo_children'):
                                        result = find_sheet_recursive(child)
                                        if result and result[0]:
                                            return result
                            except:
                                pass
                            return None, None
                        
                        sheet, _ = find_sheet_recursive(dashboard.single_view)
                        # Get cols from the UI entry if available
                        if single_view_ui:
                            cols = single_view_ui.get("cols")
                    
                    # Use a separate key for single view entries to avoid overwriting multi-view entries
                    # This ensures multi-view and single view entries are completely independent
                    single_view_key = f"_single_{symbol}"
                    
                    # Remove old single view entry if symbol changed
                    if hasattr(dashboard, 'single_view_symbol') and dashboard.single_view_symbol != symbol:
                        old_symbol = dashboard.single_view_symbol
                        old_single_key = f"_single_{old_symbol}"
                        if old_single_key in dashboard.ticker_tabs:
                            old_ui = dashboard.ticker_tabs[old_single_key]
                            # Get sheet from old entry if we don't have it yet
                            if not sheet and old_ui.get("sheet"):
                                sheet = old_ui.get("sheet")
                                cols = old_ui.get("cols")
                            # Delete old single view entry
                            del dashboard.ticker_tabs[old_single_key]
                    
                    # Always create/update single view entry under the special key
                    # This NEVER overwrites multi-view entries
                    # IMPORTANT: Do this even if there are no expirations, so single_view_symbol gets updated
                    # Make sure we have cols - get from single_view_ui if we don't have it
                    if not cols and single_view_ui:
                        cols = single_view_ui.get("cols")
                    # If still no cols, try to get headers and convert
                    if not cols and single_view_ui:
                        headers = single_view_ui.get("headers")
                        if headers:
                            # Headers should match the cols order, but we need the actual col names
                            # For now, use a default set if we can't find it
                            pass
                    
                    dashboard.ticker_tabs[single_view_key] = {
                        "tab": single_view_ui.get("tab") if single_view_ui else None,
                        "price_var": price_var,
                        "exp_var": exp_var,
                        "exp_dropdown": exp_dropdown,
                        "sheet": sheet,
                        "cols": cols,
                        "headers": single_view_ui.get("headers") if single_view_ui else None,
                        "ticker_var": ticker_var,
                        "ticker_label": ticker_label if hasattr(dashboard, 'single_view_ticker_label') else None,
                        "_is_single_view": True,
                        "_symbol": symbol  # Store the actual symbol for reference
                    }
                    
                    print(f"[SINGLE VIEW SAVE] Stored entry - sheet={sheet is not None}, cols={cols is not None}")
                    
                    # Update single_view_symbol reference - ALWAYS do this, even if no expirations
                    dashboard.single_view_symbol = symbol
                    print(f"[SINGLE VIEW SAVE] Set single_view_symbol to: {symbol}")
                    print(f"[SINGLE VIEW SAVE] Created ticker_tabs entry with key: {single_view_key}")
                    print(f"[SINGLE VIEW SAVE] ticker_tabs keys: {list(dashboard.ticker_tabs.keys())}")
                    
                    # Update expiration dropdown - ONLY update single view's components
                    if expirations:
                        # Hide "Options N/A" message if it exists
                        if hasattr(dashboard, 'single_view_options_na_label'):
                            dashboard.single_view_options_na_label.pack_forget()
                        
                        exp_dropdown.configure(values=expirations)
                        exp_var.set(expirations[0])
                        
                        # Update table - ONLY update single view entry's sheet directly
                        # The multi-view entry (if it exists) is completely untouched
                        print(f"[SINGLE VIEW SAVE] Updating table - sheet={sheet is not None}, exp_data_map={state.exp_data_map is not None}")
                        if sheet and state.exp_data_map:
                            # Clear and repopulate the single view table directly
                            # If cols not found, try to get from the stored entry
                            if not cols:
                                # Try to get cols from the single_view_key entry we just created
                                stored_entry = dashboard.ticker_tabs.get(single_view_key)
                                if stored_entry:
                                    cols = stored_entry.get("cols")
                                # If still not found, try from placeholder entry
                                if not cols:
                                    placeholder_entry = dashboard.ticker_tabs.get("_SINGLE_VIEW_PLACEHOLDER")
                                    if placeholder_entry:
                                        cols = placeholder_entry.get("cols")
                            
                            print(f"[SINGLE VIEW SAVE] cols={cols}, expirations[0]={expirations[0] if expirations else None}")
                            if cols:
                                df = state.exp_data_map.get(expirations[0])
                                print(f"[SINGLE VIEW SAVE] df={df is not None and not df.empty if df is not None else False}, rows={len(df) if df is not None and not df.empty else 0}")
                                if df is not None and not df.empty:
                                    # Convert DataFrame to list of lists for tksheet
                                    data = []
                                    for _, row in df.iterrows():
                                        data.append(format_row_data(row, cols))
                                    print(f"[SINGLE VIEW SAVE] Setting sheet data with {len(data)} rows")
                                    sheet.set_sheet_data(data)
                                    # Highlight rows based on strike price vs stock price
                                    highlight_rows_by_strike(sheet, df, cols, price)
                                else:
                                    print(f"[SINGLE VIEW SAVE] No data, clearing sheet")
                                    sheet.set_sheet_data([])
                            else:
                                print(f"[SINGLE VIEW SAVE] WARNING: cols is None, cannot update table")
                        else:
                            print(f"[SINGLE VIEW SAVE] WARNING: sheet={sheet is not None}, exp_data_map={state.exp_data_map is not None}")
                    else:
                        # No expirations - show "Options N/A" message and clear dropdown/table
                        if hasattr(dashboard, 'single_view_options_na_label'):
                            dashboard.single_view_options_na_label.pack(side="left", padx=(8, 0))
                        
                        exp_dropdown.configure(values=[])
                        if sheet:
                            sheet.set_sheet_data([])
                    
                    # Update ticker display label only after successful fetch
                    # Do this for ALL tickers, even those without options
                    if hasattr(dashboard, 'single_view_ticker_display_var'):
                        dashboard.single_view_ticker_display_var.set(symbol)
                    if hasattr(dashboard, 'single_view_ticker_label'):
                        dashboard.single_view_ticker_label.configure(text=symbol)
                    
                    # Hide autocomplete suggestions after successful fetch
                    if hasattr(dashboard, 'single_view_autocomplete'):
                        dashboard.single_view_autocomplete._hide_suggestions()
                    if hasattr(dashboard, 'single_view_autocomplete_container'):
                        dashboard.single_view_autocomplete_container.pack_forget()
                    
                    # Enable Generate Chart button only if options data exists
                    if hasattr(dashboard, 'generate_chart_button'):
                        if expirations and len(expirations) > 0:
                            dashboard.generate_chart_button.configure(state="normal")
                        else:
                            dashboard.generate_chart_button.configure(state="disabled")
                    
                    # Record ticker search in history only on successful fetch
                    record_ticker_search(symbol)
                    
                    # Show completion message for 2 seconds
                    dialogs.show_timed_message(
                        dashboard.root,
                        "Fetch Complete",
                        f"Successfully fetched options data for {symbol}",
                        duration_ms=2000
                    )
                except Exception as e:
                    print(f"[SINGLE VIEW SAVE] ERROR in update(): {e}")
                    import traceback
                    traceback.print_exc()
                    # Still try to set single_view_symbol even on error
                    try:
                        dashboard.single_view_symbol = symbol
                        print(f"[SINGLE VIEW SAVE] Set single_view_symbol to: {symbol} (after error)")
                    except:
                        pass

            dashboard.root.after(0, update)

        except Exception as e:
            dashboard.root.after(
                0, lambda: dialogs.error("Fetch Error", str(e))
            )

    threading.Thread(target=worker, daemon=True).start()

def fetch_all_stocks(self):
    # Initialize tracking for this fetch operation
    self.fetching_symbols = set(self.preset_tickers)
    self.completed_symbols = set()
    
    # Disable Generate Chart Group button when starting a new fetch
    if hasattr(self, 'generate_chart_group_button'):
        self.generate_chart_group_button.configure(state="disabled")
    
    # Show fetching dialog
    if len(self.preset_tickers) > 0:
        self.fetching_dialog = dialogs.show_fetching_dialog(
            self.root,
            "Fetching Options Data",
            "Fetching options data for all tickers..."
        )
    
    for symbol in self.preset_tickers:
        threading.Thread(
            target=fetch_worker,
            args=(self, symbol),
            daemon=True
        ).start()

def load_csv_index_data(self):
    symbol = self.csv_symbol_var.get()

    if self.csv_mode_var.get() == "Default File":
        filename = f"{symbol.lower()}_quotedata.csv"
    else:
        filename = filedialog.askopenfilename(
            title=f"Select {symbol} CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not filename:
            return

    try:
        exp_map, expirations, spot, display_symbol = load_csv_index(
            symbol,
            filename
        )

        state = TickerState(
            symbol=display_symbol,
            price=spot,
            exp_data_map=exp_map,
            last_updated=datetime.datetime.now(),
            is_csv=True
        )

        # Check if we're in single view mode
        is_single_view = hasattr(self, 'single_view') and self.single_view.winfo_viewable()
        
        # If loading in single view, preserve multi-view data and mark CSV as single-view data
        if is_single_view:
            # Backup multi-view data if it exists before overwriting
            existing_state = self.ticker_data.get(display_symbol)
            if existing_state and (not hasattr(existing_state, '_from_single_view') or not existing_state._from_single_view):
                # Backup multi-view data before overwriting
                if not hasattr(self, 'multi_view_data_backup'):
                    self.multi_view_data_backup = {}
                self.multi_view_data_backup[display_symbol] = existing_state
                print(f"[CSV LOAD] Backed up multi-view data for {display_symbol} before overwriting with CSV")
            
            # Mark CSV data as from single view so it persists
            state._from_single_view = True
        else:
            # In multi-view, preserve single-view data if it exists
            existing_state = self.ticker_data.get(display_symbol)
            if existing_state and hasattr(existing_state, '_from_single_view') and existing_state._from_single_view:
                # Don't overwrite single-view data with CSV data when in multi-view
                print(f"[CSV LOAD] Preserving single-view data for {display_symbol}, skipping CSV overwrite in multi-view")
                return
            # Mark CSV data as multi-view data
            state._from_single_view = False
        
        self.ticker_data[display_symbol] = state
        
        # Update backup if loading in single view
        if is_single_view and hasattr(self, 'single_view_data_backup'):
            self.single_view_data_backup[display_symbol] = state
        
        if is_single_view:
            # Single view mode - update the existing single view UI
            if hasattr(self, 'single_view_symbol'):
                # Get the sheet widget first - it's shared across all single view symbols
                sheet = None
                cols = None
                
                # Look for any single view entry to get the sheet widget
                single_view_ui = None
                for existing_symbol, existing_ui in self.ticker_tabs.items():
                    if existing_ui.get("_is_single_view") or "ticker_var" in existing_ui:
                        single_view_ui = existing_ui
                        sheet = existing_ui.get("sheet")
                        cols = existing_ui.get("cols")
                        break
                
                # If still not found, get sheet from single view structure
                if not sheet and hasattr(self, 'single_view') and self.single_view:
                    def find_sheet_recursive(widget):
                        try:
                            for child in widget.winfo_children():
                                if isinstance(child, Sheet):
                                    return child, child.headers()
                                if hasattr(child, 'winfo_children'):
                                    result = find_sheet_recursive(child)
                                    if result and result[0]:
                                        return result
                        except:
                            pass
                        return None, None
                    
                    sheet, _ = find_sheet_recursive(self.single_view)
                    # Get cols from the UI entry if available
                    if single_view_ui:
                        cols = single_view_ui.get("cols")
                
                # Update the single view symbol to the CSV symbol
                # Use the base symbol (without "(CSV)") for single_view_symbol to avoid issues
                # But keep display_symbol for display purposes
                old_symbol = self.single_view_symbol if hasattr(self, 'single_view_symbol') else None
                # Extract base symbol from display_symbol (remove " (CSV)" if present)
                base_symbol = display_symbol.replace(" (CSV)", "")
                self.single_view_symbol = base_symbol
                
                # Use the proper single view key format: "_single_{symbol}"
                # Use base_symbol for the key to avoid issues with "(CSV)" in keys
                single_view_key = f"_single_{base_symbol}"
                old_single_key = f"_single_{old_symbol}" if old_symbol else None
                
                # Update ticker_tabs entry with proper single view key format
                if old_single_key and old_single_key in self.ticker_tabs:
                    old_ui = self.ticker_tabs[old_single_key]
                    # Get sheet from old entry if we don't have it yet
                    if not sheet and old_ui.get("sheet"):
                        sheet = old_ui.get("sheet")
                        cols = old_ui.get("cols")
                    # Update it with new symbol key, preserving single view components
                    self.ticker_tabs[single_view_key] = old_ui
                    if old_single_key != single_view_key:
                        del self.ticker_tabs[old_single_key]
                    ui = self.ticker_tabs[single_view_key]
                    # Ensure sheet is set
                    if sheet:
                        ui["sheet"] = sheet
                        ui["cols"] = cols
                else:
                    # No old entry, create new single view entry with proper key format
                    ui = {
                        "tab": None,
                        "price_var": self.single_view_price_var,
                        "exp_var": self.single_view_exp_var,
                        "exp_dropdown": self.single_view_exp_dropdown,
                        "sheet": sheet,
                        "cols": cols,
                        "headers": single_view_ui.get("headers") if single_view_ui else None,
                        "ticker_var": self.single_view_ticker_var,
                        "ticker_label": self.single_view_ticker_label if hasattr(self, 'single_view_ticker_label') else None,
                        "_is_single_view": True
                    }
                    self.ticker_tabs[single_view_key] = ui
                
                # Update ticker input var (but not display until CSV loads successfully)
                if hasattr(self, 'single_view_ticker_var'):
                    self.single_view_ticker_var.set(display_symbol)
                # Display will be updated after CSV loads successfully below
                
                # Ensure we have the ui reference (use single_view_key, not display_symbol)
                if single_view_key not in self.ticker_tabs:
                    # If for some reason the entry wasn't created, create it now
                    ui = {
                        "tab": None,
                        "price_var": self.single_view_price_var,
                        "exp_var": self.single_view_exp_var,
                        "exp_dropdown": self.single_view_exp_dropdown,
                        "sheet": sheet,
                        "cols": cols,
                        "headers": single_view_ui.get("headers") if single_view_ui else None,
                        "ticker_var": self.single_view_ticker_var,
                        "ticker_label": self.single_view_ticker_label if hasattr(self, 'single_view_ticker_label') else None,
                        "_is_single_view": True
                    }
                    self.ticker_tabs[single_view_key] = ui
                else:
                    ui = self.ticker_tabs[single_view_key]
            else:
                dialogs.error("CSV Error", "Single view not properly initialized.")
                return
        else:
            # Multi view mode - create a new tab
            if display_symbol not in self.ticker_tabs:
                self.preset_tickers.append(display_symbol)
                self.create_stock_tab(display_symbol)
            ui = self.ticker_tabs[display_symbol]

        ui["price_var"].set(f"${spot:.2f}")

        ui["exp_dropdown"].configure(values=expirations)
        
        # Show/hide "Options N/A" message based on whether expirations exist (single view)
        if is_single_view and hasattr(self, 'single_view_options_na_label'):
            if not expirations or len(expirations) == 0:
                self.single_view_options_na_label.pack(side="left", padx=(8, 0))
            else:
                self.single_view_options_na_label.pack_forget()
        
        if expirations:
            ui["exp_var"].set(expirations[0])
            # For single view, update the table directly since we have the UI and state
            # For multi view, use update_table_for_symbol
            if is_single_view:
                # Update table directly for single view
                sheet = ui.get("sheet")
                cols = ui.get("cols")
                if sheet and cols and state.exp_data_map:
                    df = state.exp_data_map.get(expirations[0])
                    if df is not None and not df.empty:
                        # Convert DataFrame to list of lists for tksheet
                        data = []
                        for _, row in df.iterrows():
                            data.append(format_row_data(row, cols))
                        sheet.set_sheet_data(data)
                        # Highlight rows based on strike price vs stock price
                        highlight_rows_by_strike(sheet, df, cols, state.price)
                    else:
                        sheet.set_sheet_data([])
            else:
                self.update_table_for_symbol(display_symbol, expirations[0])

        # Update ticker display label only after successful CSV load (single view)
        if is_single_view:
            if hasattr(self, 'single_view_ticker_display_var'):
                self.single_view_ticker_display_var.set(display_symbol)
            if hasattr(self, 'single_view_ticker_label'):
                self.single_view_ticker_label.configure(text=display_symbol)
            
            # Hide autocomplete suggestions after successful CSV load
            if hasattr(self, 'single_view_autocomplete'):
                self.single_view_autocomplete._hide_suggestions()
            if hasattr(self, 'single_view_autocomplete_container'):
                self.single_view_autocomplete_container.pack_forget()
            
            # Enable Generate Chart button only if options data exists
            if hasattr(self, 'generate_chart_button'):
                if expirations and len(expirations) > 0:
                    self.generate_chart_button.configure(state="normal")
                else:
                    self.generate_chart_button.configure(state="disabled")

        dialogs.info(
            "CSV Loaded",
            f"{display_symbol} options loaded successfully."
        )

    except Exception as e:
        dialogs.error("CSV Error", str(e))
