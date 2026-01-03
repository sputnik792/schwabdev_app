import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import datetime
import os
import json

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
        # Tracking for fetch completion
        self.fetching_symbols = set()
        self.completed_symbols = set()

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
        self.start_auto_refresh()

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
        base_height = 120 + (rows_needed * 45)  # Header + entries + buttons
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
                
                new_height = 120 + (rows_needed * 45)
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
        tab_id = self.notebook.select()
        symbol = self.notebook.tab(tab_id, "text")
        state = self.ticker_data.get(symbol)
        exp = self.ticker_tabs[symbol]["exp_var"].get()

        open_stats_modal(self.root, state, exp)