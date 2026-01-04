import threading
import datetime

from state.ticker_state import TickerState
from data.schwab_api import fetch_stock_price, fetch_option_chain
from data.csv_loader import load_csv_index
from ui import dialogs

def fetch_worker(self, symbol):
    try:
        price = fetch_stock_price(self.client, symbol)
        exp_map, expirations = fetch_option_chain(self.client, symbol)

        state = TickerState(
            symbol=symbol,
            price=price,
            exp_data_map=exp_map,
            last_updated=datetime.datetime.now()
        )

        def update_ui():
            self.ticker_data[symbol] = state
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

            state = TickerState(
                symbol=symbol,
                price=price,
                exp_data_map=exp_map,
                last_updated=datetime.datetime.now()
            )

            def update():
                # Store data with a flag to indicate it's from single view
                # This prevents multi-view from using this data
                state._from_single_view = True
                dashboard.ticker_data[symbol] = state
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
                    # First, try to get tree from stored single view components
                    tree = None
                    cols = None
                    
                    # Look for any single view entry to get the tree widget (it's the same tree for all symbols)
                    # Single view entries use the key format "_single_{symbol}"
                    single_view_ui = None
                    for existing_key, existing_ui in dashboard.ticker_tabs.items():
                        if existing_key.startswith("_single_") and (existing_ui.get("_is_single_view") or "ticker_var" in existing_ui):
                            single_view_ui = existing_ui
                            tree = existing_ui.get("tree")
                            cols = existing_ui.get("cols")
                            break
                    
                    # If still not found, get tree from single view structure
                    if not tree and hasattr(dashboard, 'single_view') and dashboard.single_view:
                        import tkinter.ttk as ttk
                        def find_tree_recursive(widget):
                            try:
                                for child in widget.winfo_children():
                                    if isinstance(child, ttk.Treeview):
                                        return child, child['columns']
                                    if hasattr(child, 'winfo_children'):
                                        result = find_tree_recursive(child)
                                        if result and result[0]:
                                            return result
                            except:
                                pass
                            return None, None
                        
                        tree, cols = find_tree_recursive(dashboard.single_view)
                    
                    # Use a separate key for single view entries to avoid overwriting multi-view entries
                    # This ensures multi-view and single view entries are completely independent
                    single_view_key = f"_single_{symbol}"
                    
                    # Remove old single view entry if symbol changed
                    if hasattr(dashboard, 'single_view_symbol') and dashboard.single_view_symbol != symbol:
                        old_symbol = dashboard.single_view_symbol
                        old_single_key = f"_single_{old_symbol}"
                        if old_single_key in dashboard.ticker_tabs:
                            old_ui = dashboard.ticker_tabs[old_single_key]
                            # Get tree from old entry if we don't have it yet
                            if not tree and old_ui.get("tree"):
                                tree = old_ui.get("tree")
                                cols = old_ui.get("cols")
                            # Delete old single view entry
                            del dashboard.ticker_tabs[old_single_key]
                    
                    # Always create/update single view entry under the special key
                    # This NEVER overwrites multi-view entries
                    # IMPORTANT: Do this even if there are no expirations, so single_view_symbol gets updated
                    dashboard.ticker_tabs[single_view_key] = {
                        "tab": single_view_ui.get("tab") if single_view_ui else None,
                        "price_var": price_var,
                        "exp_var": exp_var,
                        "exp_dropdown": exp_dropdown,
                        "tree": tree,
                        "cols": cols,
                        "ticker_var": ticker_var,
                        "ticker_label": ticker_label if hasattr(dashboard, 'single_view_ticker_label') else None,
                        "_is_single_view": True,
                        "_symbol": symbol  # Store the actual symbol for reference
                    }
                    
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
                        
                        # Update table - ONLY update single view entry's tree directly
                        # The multi-view entry (if it exists) is completely untouched
                        if tree and state.exp_data_map:
                            # Clear and repopulate the single view table directly
                            tree.delete(*tree.get_children())
                            if cols:
                                df = state.exp_data_map.get(expirations[0])
                                if df is not None and not df.empty:
                                    import tkinter as tk
                                    for _, row in df.iterrows():
                                        tree.insert(
                                            "",
                                            tk.END,
                                            values=[row.get(c, "") for c in cols]
                                        )
                    else:
                        # No expirations - show "Options N/A" message and clear dropdown/table
                        if hasattr(dashboard, 'single_view_options_na_label'):
                            dashboard.single_view_options_na_label.pack(side="left", padx=(8, 0))
                        
                        exp_dropdown.configure(values=[])
                        if tree:
                            tree.delete(*tree.get_children())
                    
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
        from tkinter import filedialog
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

        self.ticker_data[display_symbol] = state

        # Check if we're in single view mode
        is_single_view = hasattr(self, 'single_view') and self.single_view.winfo_viewable()
        
        if is_single_view:
            # Single view mode - update the existing single view UI
            if hasattr(self, 'single_view_symbol'):
                # Get the tree widget first - it's shared across all single view symbols
                tree = None
                cols = None
                
                # Look for any single view entry to get the tree widget
                single_view_ui = None
                for existing_symbol, existing_ui in self.ticker_tabs.items():
                    if existing_ui.get("_is_single_view") or "ticker_var" in existing_ui:
                        single_view_ui = existing_ui
                        tree = existing_ui.get("tree")
                        cols = existing_ui.get("cols")
                        break
                
                # If still not found, get tree from single view structure
                if not tree and hasattr(self, 'single_view') and self.single_view:
                    from tkinter import ttk
                    def find_tree_recursive(widget):
                        try:
                            for child in widget.winfo_children():
                                if isinstance(child, ttk.Treeview):
                                    return child, child['columns']
                                if hasattr(child, 'winfo_children'):
                                    result = find_tree_recursive(child)
                                    if result and result[0]:
                                        return result
                        except:
                            pass
                        return None, None
                    
                    tree, cols = find_tree_recursive(self.single_view)
                
                # Update the single view symbol to the CSV symbol
                old_symbol = self.single_view_symbol
                self.single_view_symbol = display_symbol
                
                # Update ticker_tabs entry
                if old_symbol in self.ticker_tabs:
                    old_ui = self.ticker_tabs[old_symbol]
                    # Only move if it's a single view entry
                    if old_ui.get("_is_single_view") or "ticker_var" in old_ui:
                        # Get tree from old entry if we don't have it yet
                        if not tree and old_ui.get("tree"):
                            tree = old_ui.get("tree")
                            cols = old_ui.get("cols")
                        # Update it with new symbol key, preserving single view components
                        self.ticker_tabs[display_symbol] = old_ui
                        if old_symbol != display_symbol:
                            del self.ticker_tabs[old_symbol]
                        ui = self.ticker_tabs[display_symbol]
                        # Ensure tree is set
                        if tree:
                            ui["tree"] = tree
                            ui["cols"] = cols
                    else:
                        # Old entry is from multi-view, create new single view entry
                        ui = {
                            "tab": None,
                            "price_var": self.single_view_price_var,
                            "exp_var": self.single_view_exp_var,
                            "exp_dropdown": self.single_view_exp_dropdown,
                            "tree": tree,
                            "cols": cols,
                            "ticker_var": self.single_view_ticker_var,
                            "ticker_label": self.single_view_ticker_label if hasattr(self, 'single_view_ticker_label') else None,
                            "_is_single_view": True
                        }
                        self.ticker_tabs[display_symbol] = ui
                else:
                    # No old entry, create new single view entry
                    ui = {
                        "tab": None,
                        "price_var": self.single_view_price_var,
                        "exp_var": self.single_view_exp_var,
                        "exp_dropdown": self.single_view_exp_dropdown,
                        "tree": tree,
                        "cols": cols,
                        "ticker_var": self.single_view_ticker_var,
                        "ticker_label": self.single_view_ticker_label if hasattr(self, 'single_view_ticker_label') else None,
                        "_is_single_view": True
                    }
                    self.ticker_tabs[display_symbol] = ui
                
                # Update ticker input var (but not display until CSV loads successfully)
                if hasattr(self, 'single_view_ticker_var'):
                    self.single_view_ticker_var.set(display_symbol)
                # Display will be updated after CSV loads successfully below
                
                # Ensure we have the ui reference
                ui = self.ticker_tabs[display_symbol]
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
