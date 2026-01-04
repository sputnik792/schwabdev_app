import threading
from ui import dialogs
from data.schwab_api import fetch_stock_price, fetch_option_chain
from state.app_state import get_state_value
from ui.dashboard.tabs import reapply_highlighting_for_symbol

def start_auto_refresh(self):
    auto_refresh_price(self)
    auto_refresh_options(self)

def auto_refresh_price(self):
    # Check if auto refresh is enabled
    mode = get_state_value("ticker_refresh_mode", "auto")
    if mode != "auto":
        return  # Don't schedule next refresh if in manual mode
    
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
                    # Re-apply highlighting with new price
                    reapply_highlighting_for_symbol(self, sym)

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

    # Only schedule next refresh if in auto mode
    mode = get_state_value("ticker_refresh_mode", "auto")
    if mode == "auto":
        self.root.after(10000, lambda: auto_refresh_price(self))

def auto_refresh_options(self):
    # Check if auto refresh is enabled
    mode = get_state_value("ticker_refresh_mode", "auto")
    if mode != "auto":
        return  # Don't schedule next refresh if in manual mode
    
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

    # Only schedule next refresh if in auto mode
    mode = get_state_value("ticker_refresh_mode", "auto")
    if mode == "auto":
        self.root.after(30000, lambda: auto_refresh_options(self))

def manual_refresh_all_tickers(dashboard):
    """Manually refresh all tickers that have been fetched (both single and multi view)"""
    # Refresh prices for all tickers
    symbols = list(dashboard.ticker_data.keys())
    
    if not symbols:
        dialogs.show_timed_message(dashboard.root, "No Tickers", "No tickers to refresh", duration=2000)
        return
    
    # Show fetching dialog
    fetching_dialog = dialogs.show_fetching_dialog(dashboard.root, "Refreshing", "Refreshing all tickers...")
    
    def refresh_worker():
        refreshed_count = 0
        
        for symbol in symbols:
            state = dashboard.ticker_data.get(symbol)
            if not state or state.is_csv:
                continue
            
            # Refresh price
            try:
                price = fetch_stock_price(dashboard.client, symbol)
                if price > 0:
                    def update_price():
                        state = dashboard.ticker_data.get(symbol)
                        if state:
                            state.price = price
                            # Update UI for multi-view
                            if symbol in dashboard.ticker_tabs:
                                ui = dashboard.ticker_tabs[symbol]
                                if ui and not ui.get("_is_single_view"):
                                    ui["price_var"].set(f"${price:.2f}")
                            # Update UI for single-view
                            single_key = f"_single_{symbol}"
                            if single_key in dashboard.ticker_tabs:
                                ui = dashboard.ticker_tabs[single_key]
                                if ui and ui.get("_is_single_view"):
                                    if hasattr(dashboard, 'single_view_price_var'):
                                        dashboard.single_view_price_var.set(f"${price:.2f}")
                                    if ui.get("price_var"):
                                        ui["price_var"].set(f"${price:.2f}")
                            # Re-apply highlighting with new price
                            reapply_highlighting_for_symbol(dashboard, symbol)
                    dashboard.root.after(0, update_price)
                    refreshed_count += 1
            except:
                pass
            
            # Refresh options
            try:
                exp_map, expirations = fetch_option_chain(dashboard.client, symbol)
                if expirations:
                    def update_options():
                        state = dashboard.ticker_data.get(symbol)
                        if state:
                            state.exp_data_map = exp_map
                            # Update UI for multi-view
                            if symbol in dashboard.ticker_tabs:
                                ui = dashboard.ticker_tabs[symbol]
                                if ui and not ui.get("_is_single_view"):
                                    prev_exp = ui["exp_var"].get()
                                    ui["exp_dropdown"].configure(values=expirations)
                                    ui["exp_var"].set(prev_exp if prev_exp in expirations else expirations[0])
                                    dashboard.update_table_for_symbol(symbol, ui["exp_var"].get())
                            # Update UI for single-view
                            single_key = f"_single_{symbol}"
                            if single_key in dashboard.ticker_tabs:
                                ui = dashboard.ticker_tabs[single_key]
                                if ui and ui.get("_is_single_view"):
                                    prev_exp = None
                                    if hasattr(dashboard, 'single_view_exp_var'):
                                        prev_exp = dashboard.single_view_exp_var.get()
                                    elif ui.get("exp_var"):
                                        prev_exp = ui["exp_var"].get()
                                    
                                    if hasattr(dashboard, 'single_view_exp_dropdown'):
                                        dashboard.single_view_exp_dropdown.configure(values=expirations)
                                    if ui.get("exp_dropdown"):
                                        ui["exp_dropdown"].configure(values=expirations)
                                    
                                    selected_exp = prev_exp if prev_exp and prev_exp in expirations else expirations[0]
                                    if hasattr(dashboard, 'single_view_exp_var'):
                                        dashboard.single_view_exp_var.set(selected_exp)
                                    if ui.get("exp_var"):
                                        ui["exp_var"].set(selected_exp)
                                    
                                    dashboard.update_table_for_symbol(symbol, selected_exp)
                    dashboard.root.after(0, update_options)
            except:
                pass
        
        def close_dialog():
            fetching_dialog.destroy()
            dialogs.show_timed_message(dashboard.root, "Refresh Complete", f"Refreshed {refreshed_count} ticker(s)", duration=2000)
        
        dashboard.root.after(0, close_dialog)
    
    threading.Thread(target=refresh_worker, daemon=True).start()
