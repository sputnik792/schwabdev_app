import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import datetime
import os
import json
import re

from options_dashboard.config import MAX_TICKERS, PRESET_FILE
from options_dashboard.state.ticker_state import TickerState
from options_dashboard.data.schwab_api import fetch_stock_price, fetch_option_chain
from options_dashboard.data.csv_loader import load_csv_index
# from ui.dashboard_chart_logic import generate_selected_chart_impl
from options_dashboard.data.schwab_auth import mark_schwab_reset
from ui import dialogs
from ui.dashboard.layout import build_layout
from ui.dashboard.tabs import rebuild_tabs, create_stock_tab, update_table_for_symbol, on_expiration_change
from ui.dashboard.data_controller import fetch_worker, fetch_all_stocks, load_csv_index_data
from ui.dashboard.refresh import start_auto_refresh, auto_refresh_price, auto_refresh_options
from ui.dashboard.charts_controller import generate_selected_chart, generate_chart_group
from style.custom_theme_controller import register_theme_change_callback
from ui.dashboard.single_stock_panel import build_single_stock_panel
from ui.dashboard.stats_modal import open_stats_modal


class Dashboard(ctk.CTkFrame):
    def __init__(self, root, client):
        super().__init__(root)
        self.root = root
        self.client = client

        # ---- state ----
        self.preset_tickers = self.load_preset_tickers()
        self.ticker_tabs = {}
        self.ticker_data = {}
        self.single_view_data_backup = {}  # Backup for single-view data when multi-view overwrites it
        self.multi_view_data_backup = {}  # Backup for multi-view data when single-view overwrites it
        # Tracking for fetch completion
        self.fetching_symbols = set()
        self.completed_symbols = set()
        
        # CSV variables (initialized early for data_controller access)
        self.csv_symbol_var = tk.StringVar(value="SPX")
        self.csv_mode_var = tk.StringVar(value="Default File")

        # ---- binding controllers ----
        self.build_layout = build_layout.__get__(self)
        self.rebuild_tabs = rebuild_tabs.__get__(self)
        self.create_stock_tab = create_stock_tab.__get__(self)
        self.update_table_for_symbol = update_table_for_symbol.__get__(self)
        self.on_expiration_change = on_expiration_change.__get__(self)

        self.fetch_worker = fetch_worker.__get__(self)
        self.fetch_all_stocks = fetch_all_stocks.__get__(self)
        self.load_csv_index_data = load_csv_index_data.__get__(self)

        self.start_auto_refresh = start_auto_refresh.__get__(self)
        self.auto_refresh_price = auto_refresh_price.__get__(self)
        self.auto_refresh_options = auto_refresh_options.__get__(self)

        self.generate_selected_chart = generate_selected_chart.__get__(self)
        self.generate_chart_group = generate_chart_group.__get__(self)
        from ui.dashboard.charts_controller import _bring_chart_windows_to_front
        self._bring_chart_windows_to_front = _bring_chart_windows_to_front.__get__(self)
        #---- end of binding controllers

        # ---- layout ----
        self.pack(fill="both", expand=True)
        # Bind view methods BEFORE build_layout so toggle callback can use them
        from ui.dashboard.layout import show_multi_view, show_single_view
        self.show_multi_view = show_multi_view.__get__(self)
        self.show_single_view = show_single_view.__get__(self)
        self.build_layout()
        # Initialize view based on saved state
        from state.app_state import get_state_value
        saved_view_mode = get_state_value("view_mode", "multi")
        if saved_view_mode == "single":
            self.show_single_view()
        else:
            self.show_multi_view()
        register_theme_change_callback(self.rebuild)
        # Rebuild tabs will be called in show_multi_view if needed
        # Defer auto-refresh start to avoid blocking startup
        # Only start auto-refresh if mode is set to "auto"
        from state.app_state import get_state_value
        refresh_mode = get_state_value("ticker_refresh_mode", "auto")
        if refresh_mode == "auto":
            self.root.after(100, self.start_auto_refresh)
        
        # Update refresh button visibility based on saved mode
        from ui.dashboard.layout import update_refresh_button_visibility
        self.root.after(200, lambda: update_refresh_button_visibility(self))

    def rebuild(self):
        self.destroy()
        Dashboard(self.root, self.client)

    def load_preset_tickers(self):
        if os.path.exists(PRESET_FILE):
            try:
                with open(PRESET_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [s.upper() for s in data][:MAX_TICKERS]
            except Exception:
                pass
        return ["SPY"]

    def save_preset_tickers(self):
        try:
            with open(PRESET_FILE, "w") as f:
                json.dump(self.preset_tickers, f, indent=2)
        except Exception as e:
            dialogs.error("Error", f"Failed to save presets:\n{e}")

    def edit_tickers(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Edit Preset Tickers")
        win.resizable(True, True)  # Enable resizing and maximize button
        win.minsize(400, 200)
        
        # Explicitly enable maximize button (Windows)
        try:
            win.attributes('-toolwindow', False)  # Ensure it's not a tool window
        except:
            pass
        
        win.lift()  # Bring to front
        win.focus()  # Give it focus
        win.grab_set()  # Make it modal

        # Track if user has manually resized the window
        user_manually_resized = [False]

        def on_configure(event):
            # Track manual window resizing
            if event.widget == win:
                user_manually_resized[0] = True

        win.bind('<Configure>', on_configure)

        # Calculate initial window size based on current ticker count
        initial_count = len(self.preset_tickers)
        # Base size: width for 2 columns, height based on rows needed
        if initial_count == 0:
            rows_needed = 1
        elif initial_count <= 12:
            rows_needed = initial_count
        else:
            left_count = 12
            right_count = initial_count - 12
            rows_needed = max(left_count, right_count)
        base_height = 180 + (rows_needed * 45)  # Header + entries + buttons (increased from 120 to 180 to show save button)
        win.geometry(f"500x{base_height}")

        # Main container
        main_frame = ctk.CTkFrame(win)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Container for two columns
        columns_frame = ctk.CTkFrame(main_frame)
        columns_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left column frame
        left_column = ctk.CTkFrame(columns_frame)
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Right column frame
        right_column = ctk.CTkFrame(columns_frame)
        right_column.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # Store entry widgets and their StringVars
        entry_widgets = []
        entry_vars = []
        current_values = self.preset_tickers.copy()

        def update_layout():
            """Rebuild the layout based on current entry count"""
            # Clear existing entries
            for widget in entry_widgets:
                widget.destroy()
            entry_widgets.clear()
            entry_vars.clear()

            num_entries = len(current_values)

            # Distribute entries across two columns
            # First 12 entries go in left column, next 12 go in right column
            for i in range(num_entries):
                var = tk.StringVar(value=current_values[i] if i < len(current_values) else "")
                entry_vars.append(var)
                
                # Determine which column (0-11 in left, 12-23 in right)
                if i < 12:
                    parent = left_column
                else:
                    parent = right_column
                
                entry = ctk.CTkEntry(parent, textvariable=var, width=200)
                entry.pack(pady=4, padx=10, fill="x")
                entry_widgets.append(entry)

            # Update button states
            num_entries = len(entry_widgets)
            add_btn.configure(state="normal" if num_entries < MAX_TICKERS else "disabled")
            remove_btn.configure(state="normal" if num_entries > 1 else "disabled")

            # Only auto-resize window if user hasn't manually resized it
            if not user_manually_resized[0]:
                # Update window size
                # Calculate rows needed: if entries <= 12, use left column only, else use both
                if num_entries == 0:
                    rows_needed = 1
                elif num_entries <= 12:
                    rows_needed = num_entries
                else:
                    # Both columns are used, calculate max rows needed
                    # Left column always has 12 (or less if total < 12), right column has the rest
                    left_count = 12
                    right_count = num_entries - 12
                    rows_needed = max(left_count, right_count)
                
                new_height = 180 + (rows_needed * 45)  # Increased from 120 to 180 to show save button
                win.geometry(f"500x{new_height}")

        def add_ticker():
            # Add a new empty ticker
            if len(current_values) < MAX_TICKERS:
                current_values.append("")
                update_layout()

        def remove_ticker():
            # Remove the last ticker
            if len(current_values) > 1:
                # Check if the last ticker has a value
                last_ticker = current_values[-1].strip() if current_values else ""
                
                # If ticker has a value, ask for confirmation
                if last_ticker:
                    # Ensure window is on top before showing dialog
                    win.lift()
                    win.focus()
                    win.update()
                    
                    # Temporarily set window to topmost to prevent it from going behind
                    try:
                        win.attributes('-topmost', True)
                        result = dialogs.ask_yes_no("Confirm Removal", f"Are you sure you want to remove '{last_ticker}'?")
                        win.attributes('-topmost', False)
                    except:
                        result = dialogs.ask_yes_no("Confirm Removal", f"Are you sure you want to remove '{last_ticker}'?")
                    
                    # Bring window back to front after dialog
                    win.lift()
                    win.focus()
                    win.update()
                    
                    if not result:
                        return  # User cancelled
                
                current_values.pop()
                update_layout()

        # Control buttons frame
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", padx=10, pady=5)

        add_btn = ctk.CTkButton(control_frame, text="+", width=50, command=add_ticker)
        add_btn.pack(side="left", padx=5)

        remove_btn = ctk.CTkButton(control_frame, text="-", width=50, command=remove_ticker)
        remove_btn.pack(side="left", padx=5)

        # Save button frame
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", padx=10, pady=10)

        def save():
            self.preset_tickers = [
                v.get().strip().upper()
                for v in entry_vars
                if v.get().strip()
            ][:MAX_TICKERS]

            self.save_preset_tickers()
            self.rebuild_tabs()
            win.grab_release()  # Release grab before destroying
            win.destroy()

        ctk.CTkButton(button_frame, text="Save", command=save).pack(pady=10)

        # Initialize layout with current tickers
        update_layout()

    def open_stats(self):
        # Check if we're in single view mode
        if hasattr(self, 'single_view') and self.single_view.winfo_viewable():
            # Single view mode - use single_view_symbol
            if not hasattr(self, 'single_view_symbol'):
                dialogs.warning("No Ticker", "Please enter and fetch a ticker symbol first.")
                return
            symbol = self.single_view_symbol
        else:
            # Multi view mode - use notebook
            if not hasattr(self, 'notebook'):
                dialogs.warning("No Tabs", "No tabs available.")
                return
            tab_id = self.notebook.select()
            if not tab_id:
                return
            symbol = self.notebook.tab(tab_id, "text")
        
        state = self.ticker_data.get(symbol)
        if not state:
            dialogs.warning("No Data", "No data available for this ticker.")
            return
        
        ui = self.ticker_tabs.get(symbol)
        if not ui:
            dialogs.warning("No Data", "No UI data available for this ticker.")
            return
        
        exp = ui["exp_var"].get()
        if not exp:
            dialogs.warning("No Expiration", "Please select an expiration date.")
            return

        open_stats_modal(self.root, state, exp)

    def edit_api_credentials(self):
        """Open window to edit API credentials"""
        from options_dashboard.config import APP_KEY, SECRET
        
        win = ctk.CTkToplevel(self.root)
        win.title("Edit API Credentials")
        win.geometry("500x300")
        win.resizable(False, False)
        win.transient(self.root)
        win.lift()
        win.focus()
        win.grab_set()
        
        # Main container
        main_frame = ctk.CTkFrame(win)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # App Key
        ctk.CTkLabel(main_frame, text="App Key:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 5))
        app_key_var = tk.StringVar(value=APP_KEY)
        app_key_entry = ctk.CTkEntry(main_frame, textvariable=app_key_var, width=450)
        app_key_entry.pack(fill="x", pady=(0, 15))
        
        # Secret Key with show/hide toggle
        secret_label_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        secret_label_frame.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(secret_label_frame, text="Secret Key:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        # Toggle button for show/hide
        show_secret_var = tk.BooleanVar(value=False)
        
        def toggle_secret_visibility():
            if show_secret_var.get():
                secret_entry.configure(show="")
                show_secret_btn.configure(text="Hide")
            else:
                secret_entry.configure(show="*")
                show_secret_btn.configure(text="Show")
        
        show_secret_btn = ctk.CTkButton(
            secret_label_frame,
            text="Show",
            width=60,
            height=24,
            font=ctk.CTkFont(size=11),
            command=lambda: (show_secret_var.set(not show_secret_var.get()), toggle_secret_visibility())
        )
        show_secret_btn.pack(side="right", padx=(10, 0))
        
        secret_var = tk.StringVar(value=SECRET)
        secret_entry = ctk.CTkEntry(main_frame, textvariable=secret_var, width=450, show="*")
        secret_entry.pack(fill="x", pady=(0, 20))
        
        # Button frame
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(10, 0))
        
        def save_credentials():
            new_app_key = app_key_var.get().strip()
            new_secret = secret_var.get().strip()
            
            if not new_app_key or not new_secret:
                dialogs.warning("Invalid Input", "Both App Key and Secret Key are required.")
                return
            
            try:
                # Read current config.py - get path from config module
                import options_dashboard.config as config_module
                from pathlib import Path
                config_path = Path(config_module.__file__).resolve()
                
                with open(config_path, "r") as f:
                    content = f.read()
                
                # Replace APP_KEY and SECRET values
                content = re.sub(
                    r'APP_KEY\s*=\s*"[^"]*"',
                    f'APP_KEY = "{new_app_key}"',
                    content
                )
                content = re.sub(
                    r'SECRET\s*=\s*"[^"]*"',
                    f'SECRET = "{new_secret}"',
                    content
                )
                
                # Write back to config.py
                with open(config_path, "w") as f:
                    f.write(content)
                
                dialogs.info("Success", "API credentials saved successfully.\nPlease restart the application for changes to take effect.")
                win.grab_release()
                win.destroy()
                
            except Exception as e:
                dialogs.error("Error", f"Failed to save credentials:\n{e}")
        
        ctk.CTkButton(
            button_frame,
            text="Confirm",
            command=save_credentials,
            width=120
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=lambda: (win.grab_release(), win.destroy()),
            width=120,
            fg_color="transparent",
            border_width=1
        ).pack(side="right")