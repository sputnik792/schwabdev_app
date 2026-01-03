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
                ui["exp_dropdown"]["values"] = expirations
                ui["exp_var"].set(expirations[0])
                self.update_table_for_symbol(symbol, expirations[0])
            
            # Mark this symbol as completed
            if hasattr(self, 'fetching_symbols') and hasattr(self, 'completed_symbols'):
                self.completed_symbols.add(symbol)
                
                # Check if all symbols are done
                if self.completed_symbols == self.fetching_symbols:
                    # All done! Show the completion message
                    dialogs.show_timed_message(
                        self.root,
                        "Fetch Complete",
                        f"All {len(self.fetching_symbols)} tickers loaded successfully!",
                        3000
                    )
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
                ui["exp_dropdown"]["values"] = expirations
                ui["exp_var"].set(expirations[0])

                dashboard.update_table_for_symbol(symbol, expirations[0])

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

        if display_symbol not in self.ticker_tabs:
            self.preset_tickers.append(display_symbol)
            self.create_stock_tab(display_symbol)

        ui = self.ticker_tabs[display_symbol]
        ui["price_var"].set(f"${spot:.2f}")

        ui["exp_dropdown"]["values"] = expirations
        if expirations:
            ui["exp_var"].set(expirations[0])
            self.update_table_for_symbol(display_symbol, expirations[0])

        dialogs.info(
            "CSV Loaded",
            f"{display_symbol} options loaded successfully."
        )

    except Exception as e:
        dialogs.error("CSV Error", str(e))
