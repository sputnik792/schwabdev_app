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
                dashboard.ticker_data[symbol] = state
                
                # Update ticker input (but not display until fetch succeeds)
                ticker_var.set(symbol)
                # Don't update display label here - it will be updated after successful fetch
                
                # Update price
                price_var.set(f"${price:.2f}" if price else "—")
                
                # Update expiration dropdown
                if expirations:
                    exp_dropdown.configure(values=expirations)
                    exp_var.set(expirations[0])
                    
                    # Update the ticker_tabs entry for this symbol
                    # Remove old entry if symbol changed
                    if hasattr(dashboard, 'single_view_symbol') and dashboard.single_view_symbol != symbol:
                        old_symbol = dashboard.single_view_symbol
                        if old_symbol in dashboard.ticker_tabs:
                            # Get the UI entry before deleting
                            ui = dashboard.ticker_tabs[old_symbol]
                            # Update it with new symbol key
                            dashboard.ticker_tabs[symbol] = ui
                            if old_symbol != symbol:
                                del dashboard.ticker_tabs[old_symbol]
                    
                    # Ensure entry exists in ticker_tabs
                    if symbol not in dashboard.ticker_tabs:
                        # Get the existing UI components from single view
                        if hasattr(dashboard, 'single_view_symbol') and dashboard.single_view_symbol in dashboard.ticker_tabs:
                            ui = dashboard.ticker_tabs[dashboard.single_view_symbol]
                            dashboard.ticker_tabs[symbol] = ui
                        else:
                            # Get tree from single view if available
                            tree = None
                            cols = None
                            if hasattr(dashboard, 'single_view') and dashboard.single_view:
                                # Try to find the tree widget
                                for widget in dashboard.single_view.winfo_children():
                                    if hasattr(widget, 'winfo_children'):
                                        for child in widget.winfo_children():
                                            if isinstance(child, tk.ttk.Treeview):
                                                tree = child
                                                cols = child['columns']
                                                break
                            
                            # Create entry with UI components
                            dashboard.ticker_tabs[symbol] = {
                                "tab": None,
                                "price_var": price_var,
                                "exp_var": exp_var,
                                "exp_dropdown": exp_dropdown,
                                "tree": tree,
                                "cols": cols
                            }
                    else:
                        # Update existing entry with current UI components
                        ui = dashboard.ticker_tabs[symbol]
                        ui["price_var"] = price_var
                        ui["exp_var"] = exp_var
                        ui["exp_dropdown"] = exp_dropdown
                    
                    # Update table
                    dashboard.update_table_for_symbol(symbol, expirations[0])
                    
                    # Update single_view_symbol reference
                    dashboard.single_view_symbol = symbol
                    
                    # Update ticker display label only after successful fetch
                    if hasattr(dashboard, 'single_view_ticker_display_var'):
                        dashboard.single_view_ticker_display_var.set(symbol)
                    if hasattr(dashboard, 'single_view_ticker_label'):
                        dashboard.single_view_ticker_label.configure(text=symbol)
                    
                    # Enable Generate Chart button if it exists
                    if hasattr(dashboard, 'generate_chart_button'):
                        dashboard.generate_chart_button.configure(state="normal")
                    
                    # Show completion message for 2 seconds
                    dialogs.show_timed_message(
                        dashboard.root,
                        "Fetch Complete",
                        f"Successfully fetched options data for {symbol}",
                        duration_ms=2000
                    )

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
                # Update the single view symbol to the CSV symbol
                old_symbol = self.single_view_symbol
                self.single_view_symbol = display_symbol
                
                # Update ticker_tabs entry
                if old_symbol in self.ticker_tabs:
                    ui = self.ticker_tabs[old_symbol]
                    self.ticker_tabs[display_symbol] = ui
                    if old_symbol != display_symbol:
                        del self.ticker_tabs[old_symbol]
                else:
                    # Get UI components from single view
                    if hasattr(self, 'single_view_ticker_var'):
                        ui = {
                            "tab": None,
                            "price_var": self.single_view_price_var,
                            "exp_var": self.single_view_exp_var,
                            "exp_dropdown": self.single_view_exp_dropdown,
                            "tree": None,  # Will be found below
                            "cols": None
                        }
                        # Find the tree widget
                        if hasattr(self, 'single_view') and self.single_view:
                            from tkinter import ttk
                            for widget in self.single_view.winfo_children():
                                if hasattr(widget, 'winfo_children'):
                                    for child in widget.winfo_children():
                                        if isinstance(child, ttk.Treeview):
                                            ui["tree"] = child
                                            ui["cols"] = child['columns']
                                            break
                        self.ticker_tabs[display_symbol] = ui
                
                # Update ticker input var (but not display until CSV loads successfully)
                if hasattr(self, 'single_view_ticker_var'):
                    self.single_view_ticker_var.set(display_symbol)
                # Display will be updated after CSV loads successfully below
                
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
        if expirations:
            ui["exp_var"].set(expirations[0])
            self.update_table_for_symbol(display_symbol, expirations[0])

        # Update ticker display label only after successful CSV load (single view)
        if is_single_view:
            if hasattr(self, 'single_view_ticker_display_var'):
                self.single_view_ticker_display_var.set(display_symbol)
            if hasattr(self, 'single_view_ticker_label'):
                self.single_view_ticker_label.configure(text=display_symbol)
            # Enable Generate Chart button if it exists
            if hasattr(self, 'generate_chart_button'):
                self.generate_chart_button.configure(state="normal")

        dialogs.info(
            "CSV Loaded",
            f"{display_symbol} options loaded successfully."
        )

    except Exception as e:
        dialogs.error("CSV Error", str(e))
