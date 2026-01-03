import threading
from ui import dialogs
from data.schwab_api import fetch_stock_price, fetch_option_chain

def start_auto_refresh(self):
    auto_refresh_price(self)
    auto_refresh_options(self)

def auto_refresh_price(self):
    symbols = list(self.ticker_data.keys())

    for symbol in symbols:
        state = self.ticker_data.get(symbol)
        if not state or state.is_csv:
            continue

        def worker(sym=symbol):
            try:
                price = fetch_stock_price(self.client, sym)
                if price <= 0:
                    return

                def update():
                    state = self.ticker_data.get(sym)
                    ui = self.ticker_tabs.get(sym)
                    if not state or not ui:
                        return
                    
                    # Skip if this data was fetched in single view
                    if hasattr(state, '_from_single_view') and state._from_single_view:
                        return
                    
                    # Skip if this is a single view entry (uses _single_ prefix)
                    if sym.startswith("_single_"):
                        return

                    state.price = price
                    ui["price_var"].set(f"${price:.2f}")

                self.root.after(0, update)

            except RuntimeError as e:
                if str(e) == "AUTH_REQUIRED":
                    self.root.after(
                        0,
                        lambda: dialogs.error(
                            "Authentication Required",
                            "Schwab authentication expired.\nPlease reconnect."
                        )
                    )
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    self.root.after(10000, lambda: auto_refresh_price(self))

def auto_refresh_options(self):
    symbols = list(self.ticker_data.keys())

    for symbol in symbols:
        state = self.ticker_data.get(symbol)
        if not state or state.is_csv:
            continue

        def worker(sym=symbol):
            try:
                exp_map, expirations = fetch_option_chain(self.client, sym)
                if not expirations:
                    return

                def update():
                    state = self.ticker_data.get(sym)
                    ui = self.ticker_tabs.get(sym)
                    if not state or not ui:
                        return
                    
                    # Skip if this data was fetched in single view
                    if hasattr(state, '_from_single_view') and state._from_single_view:
                        return
                    
                    # Skip if this is a single view entry (uses _single_ prefix)
                    if sym.startswith("_single_"):
                        return

                    prev_exp = ui["exp_var"].get()
                    state.exp_data_map = exp_map

                    ui["exp_dropdown"].configure(values=expirations)
                    ui["exp_var"].set(
                        prev_exp if prev_exp in expirations else expirations[0]
                    )

                    self.update_table_for_symbol(sym, ui["exp_var"].get())

                self.root.after(0, update)

            except RuntimeError as e:
                if str(e) == "AUTH_REQUIRED":
                    self.root.after(
                        0,
                        lambda: dialogs.error(
                            "Authentication Required",
                            "Schwab authentication expired.\nPlease reconnect."
                        )
                    )
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    self.root.after(30000, lambda: auto_refresh_options(self))
