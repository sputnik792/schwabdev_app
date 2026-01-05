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
from ui.dashboard.charts_controller import _bring_chart_windows_to_front


class Dashboard(ctk.CTkFrame):
    def __init__(self, root, client):
        super().__init__(root)
        self.root = root
        self.client = client

        # ---- state ----
        # Restore data from previous dashboard instance if it exists (e.g., after theme change)
        print(f"[DASHBOARD INIT] Checking for saved dashboard state...")
        print(f"[DASHBOARD INIT] hasattr(root, '_dashboard_state'): {hasattr(root, '_dashboard_state')}")
        if hasattr(root, '_dashboard_state'):
            saved_state = root._dashboard_state
            print(f"[DASHBOARD INIT] Found saved state!")
            print(f"[DASHBOARD INIT] Saved ticker_data keys: {list(saved_state.get('ticker_data', {}).keys())}")
            print(f"[DASHBOARD INIT] Saved preset_tickers: {saved_state.get('preset_tickers', [])}")
            print(f"[DASHBOARD INIT] Saved single_view_symbol: {saved_state.get('single_view_symbol', None)}")
            
            self.ticker_data = saved_state.get('ticker_data', {}).copy()
            self.preset_tickers = saved_state.get('preset_tickers', self.load_preset_tickers()).copy()
            self.single_view_data_backup = saved_state.get('single_view_data_backup', {}).copy()
            self.multi_view_data_backup = saved_state.get('multi_view_data_backup', {}).copy()
            # Store single_view_symbol to restore later
            self._restored_single_view_symbol = saved_state.get('single_view_symbol', None)
            
            print(f"[DASHBOARD INIT] Restored ticker_data keys: {list(self.ticker_data.keys())}")
            print(f"[DASHBOARD INIT] Restored ticker_data count: {len(self.ticker_data)}")
            print(f"[DASHBOARD INIT] Restored preset_tickers: {self.preset_tickers}")
            print(f"[DASHBOARD INIT] Restored single_view_symbol: {self._restored_single_view_symbol}")
            
            # Clear the saved state so it doesn't persist beyond this rebuild
            delattr(root, '_dashboard_state')
            print(f"[DASHBOARD INIT] Cleared saved state from root")
        else:
            print(f"[DASHBOARD INIT] No saved state found, initializing fresh")
            self.preset_tickers = self.load_preset_tickers()
            self.ticker_data = {}
            self.single_view_data_backup = {}  # Backup for single-view data when multi-view overwrites it
            self.multi_view_data_backup = {}  # Backup for multi-view data when single-view overwrites it
            self._restored_single_view_symbol = None
        
        self.ticker_tabs = {}
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
        self._bring_chart_windows_to_front = _bring_chart_windows_to_front.__get__(self)
        #---- end of binding controllers

        # ---- layout ----
        self.pack(fill="both", expand=True)
        # Bind view methods BEFORE build_layout so toggle callback can use them
        from ui.dashboard.layout import show_multi_view, show_single_view
        self.show_multi_view = show_multi_view.__get__(self)
        self.show_single_view = show_single_view.__get__(self)
        self.build_layout()
        
        # Restore single_view_symbol if we restored data and were in single view
        if hasattr(self, '_restored_single_view_symbol') and self._restored_single_view_symbol:
            self.single_view_symbol = self._restored_single_view_symbol
            print(f"[DASHBOARD INIT] Restored single_view_symbol: {self.single_view_symbol}")
        
        # Initialize view based on saved state
        from state.app_state import get_state_value
        saved_view_mode = get_state_value("view_mode", "multi")
        print(f"[DASHBOARD INIT] Saved view_mode: {saved_view_mode}")
        if saved_view_mode == "single":
            print(f"[DASHBOARD INIT] Calling show_single_view()")
            self.show_single_view()
        else:
            print(f"[DASHBOARD INIT] Calling show_multi_view()")
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
        # Save dashboard state to root window so it persists across rebuild
        # This preserves option data when color theme changes
        print(f"[REBUILD] Saving dashboard state before rebuild...")
        print(f"[REBUILD] ticker_data keys: {list(self.ticker_data.keys())}")
        print(f"[REBUILD] ticker_data count: {len(self.ticker_data)}")
        print(f"[REBUILD] preset_tickers: {self.preset_tickers}")
        print(f"[REBUILD] single_view_symbol: {getattr(self, 'single_view_symbol', None)}")
        print(f"[REBUILD] single_view_data_backup keys: {list(self.single_view_data_backup.keys()) if hasattr(self, 'single_view_data_backup') else 'N/A'}")
        print(f"[REBUILD] multi_view_data_backup keys: {list(self.multi_view_data_backup.keys()) if hasattr(self, 'multi_view_data_backup') else 'N/A'}")
        
        self.root._dashboard_state = {
            'ticker_data': self.ticker_data.copy(),
            'preset_tickers': self.preset_tickers.copy(),
            'single_view_data_backup': self.single_view_data_backup.copy() if hasattr(self, 'single_view_data_backup') else {},
            'multi_view_data_backup': self.multi_view_data_backup.copy() if hasattr(self, 'multi_view_data_backup') else {},
            'single_view_symbol': getattr(self, 'single_view_symbol', None),
        }
        print(f"[REBUILD] Saved state to root._dashboard_state")
        print(f"[REBUILD] Saved ticker_data keys: {list(self.root._dashboard_state['ticker_data'].keys())}")
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
        is_single_view = (hasattr(self, 'single_view') and 
                          self.single_view is not None and 
                          self.single_view.winfo_viewable())
        
        if is_single_view:
            # Single view mode - use single_view_symbol
            if not hasattr(self, 'single_view_symbol') or not self.single_view_symbol:
                dialogs.warning("No Ticker", "Please enter and fetch a ticker symbol first.")
                return
            symbol = self.single_view_symbol
            # For single view, use the "_single_{symbol}" key format
            ticker_tabs_key = f"_single_{symbol}"
        else:
            # Multi view mode - use notebook
            if not hasattr(self, 'notebook'):
                dialogs.warning("No Tabs", "No tabs available.")
                return
            tab_id = self.notebook.select()
            if not tab_id:
                dialogs.warning("No Tab Selected", "Please select a tab.")
                return
            symbol = self.notebook.tab(tab_id, "text")
            # For multi view, use the symbol directly as the key
            ticker_tabs_key = symbol
        
        state = self.ticker_data.get(symbol)
        if not state:
            dialogs.warning("No Data", "No data available for this ticker.")
            return
        
        ui = self.ticker_tabs.get(ticker_tabs_key)
        if not ui:
            dialogs.warning("No Data", "No UI data available for this ticker.")
            return
        
        exp = ui["exp_var"].get()
        if not exp:
            dialogs.warning("No Expiration", "Please select an expiration date.")
            return

        open_stats_modal(self.root, state, exp, symbol)

    def open_data_analysis_tools(self):
        """Open the Data Analysis Tools window"""
        win = ctk.CTkToplevel(self.root)
        win.title("Data Analysis Tools")
        win.geometry("600x400")
        win.resizable(False, False)
        
        # Center the window
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        win_w = win.winfo_width()
        win_h = win.winfo_height()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # Ensure window stays in front
        win.lift()
        win.focus()
        win.attributes("-topmost", True)
        win.after(100, lambda: win.attributes("-topmost", False))
        
        # Main container
        main_frame = ctk.CTkFrame(win)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="Data Analysis Tools",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Three columns container
        columns_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True)
        
        # Quantitative (Greeks) column
        quantitative_frame = ctk.CTkFrame(columns_frame)
        quantitative_frame.pack(side="left", fill="both", expand=True, padx=10)
        
        quantitative_label = ctk.CTkLabel(
            quantitative_frame,
            text="Quantitative (Greeks)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        quantitative_label.pack(pady=(10, 10))
        
        def open_gamma_profile():
            # Check if we're in single view mode
            is_single_view = (hasattr(self, 'single_view') and 
                              self.single_view is not None and 
                              self.single_view.winfo_viewable())
            
            if is_single_view:
                # Single view mode - use single_view_symbol
                if not hasattr(self, 'single_view_symbol') or not self.single_view_symbol:
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
                    dialogs.warning("No Tab Selected", "Please select a tab.")
                    return
                symbol = self.notebook.tab(tab_id, "text")
            
            state = self.ticker_data.get(symbol)
            if not state:
                dialogs.warning("No Data", "No data available for this ticker.")
                return
            
            # Get the selected expiration date
            if is_single_view:
                # For single view, use the "_single_{symbol}" key format
                ticker_tabs_key = f"_single_{symbol}"
            else:
                # For multi view, use the symbol directly as the key
                ticker_tabs_key = symbol
            
            ui = self.ticker_tabs.get(ticker_tabs_key)
            if not ui:
                dialogs.warning("No Data", "No UI data available for this ticker.")
                return
            
            exp = ui["exp_var"].get()
            if not exp:
                dialogs.warning("No Expiration", "Please select an expiration date.")
                return
            
            from models.data_analysis.quantitative.gamma_profile import generate_gamma_profile
            generate_gamma_profile(self, symbol, state, exp)
        
        gamma_profile_btn = ctk.CTkButton(
            quantitative_frame,
            text="Gamma Profile",
            command=open_gamma_profile,
            width=150
        )
        gamma_profile_btn.pack(pady=5)
        
        # Pricing column
        pricing_frame = ctk.CTkFrame(columns_frame)
        pricing_frame.pack(side="left", fill="both", expand=True, padx=10)
        
        pricing_label = ctk.CTkLabel(
            pricing_frame,
            text="Pricing",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        pricing_label.pack(pady=(10, 10))
        
        # Experimental column
        experimental_frame = ctk.CTkFrame(columns_frame)
        experimental_frame.pack(side="left", fill="both", expand=True, padx=10)
        
        experimental_label = ctk.CTkLabel(
            experimental_frame,
            text="Experimental",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        experimental_label.pack(pady=(10, 10))

    def open_group_settings(self):
        """Open the Group Settings window"""
        from state.app_state import get_state_value, set_state_value
        import tkinter as tk
        import customtkinter as ctk
        
        # Load existing settings
        group_settings = get_state_value("group_settings", {})
        
        # Create window
        win = ctk.CTkToplevel(self.root)
        win.title("Group Settings")
        win.geometry("800x600")
        win.resizable(True, True)
        
        # Center the window
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        win_w = win.winfo_width()
        win_h = win.winfo_height()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # Ensure window stays in front
        win.lift()
        win.focus()
        win.attributes("-topmost", True)
        win.after(100, lambda: win.attributes("-topmost", False))
        
        # Keep window in front when it receives focus or is shown
        def keep_in_front(event=None):
            win.lift()
            win.focus()
        
        win.bind("<FocusIn>", keep_in_front)
        win.bind("<Map>", keep_in_front)  # When window is shown
        
        # Main container with scrollbars
        main_frame = ctk.CTkFrame(win)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Get background color for canvas (handle tuple for light/dark mode)
        bg_color_tuple = main_frame.cget("fg_color")
        # If it's a tuple, get the appropriate one based on current theme
        if isinstance(bg_color_tuple, (tuple, list)) and len(bg_color_tuple) == 2:
            from style.theme_controller import is_light_mode
            bg_color = bg_color_tuple[0] if is_light_mode() else bg_color_tuple[1]
        elif isinstance(bg_color_tuple, str):
            bg_color = bg_color_tuple
        else:
            # Fallback to a default color
            bg_color = "#1e1e1e" if ctk.get_appearance_mode() == "Dark" else "#f0f0f0"
        
        # Create scrollable frame
        canvas = tk.Canvas(main_frame, bg=bg_color, highlightthickness=0)
        scrollbar_v = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollbar_h = tk.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)
        scrollable_frame = ctk.CTkFrame(canvas)
        
        def update_scroll_region(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_v.set)
        canvas.configure(xscrollcommand=scrollbar_h.set)
        
        # Pack scrollbars and canvas
        scrollbar_v.pack(side="right", fill="y")
        scrollbar_h.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Update canvas window to fill canvas width
        def update_canvas_window(e):
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been rendered
                canvas.itemconfig(canvas_window, width=canvas_width)
        
        canvas.bind("<Configure>", update_canvas_window)
        
        # Get all tickers from preset_tickers
        tickers = self.preset_tickers if hasattr(self, 'preset_tickers') else []
        
        # Create columns (12 tickers per column)
        TICKERS_PER_COLUMN = 12
        num_columns = max(1, (len(tickers) + TICKERS_PER_COLUMN - 1) // TICKERS_PER_COLUMN)
        
        # Store references to widgets
        ticker_widgets = {}
        
        # Header row - create header for each column
        header_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Create column frames
        column_frames = []
        for col_idx in range(num_columns):
            # Header column
            header_col = ctk.CTkFrame(header_frame, fg_color="transparent")
            header_col.pack(side="left", padx=10)
            
            ctk.CTkLabel(header_col, text="Ticker", font=ctk.CTkFont(weight="bold"), width=80).pack(side="left", padx=5)
            ctk.CTkLabel(header_col, text="Include", font=ctk.CTkFont(weight="bold"), width=20).pack(side="left", padx=5)
            ctk.CTkLabel(header_col, text="Range", font=ctk.CTkFont(weight="bold"), width=100).pack(side="left", padx=5)
            
            # Data column
            col_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
            col_frame.pack(side="left", fill="y", padx=10)
            column_frames.append(col_frame)
        
        # Add tickers to columns
        for idx, ticker in enumerate(tickers):
            col_idx = idx // TICKERS_PER_COLUMN
            col_frame = column_frames[col_idx]
            
            # Get saved settings for this ticker
            ticker_settings = group_settings.get(ticker, {"include": True, "range": "1 day"})
            
            # Ticker row
            row_frame = ctk.CTkFrame(col_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            # Ticker label
            ticker_label = ctk.CTkLabel(row_frame, text=ticker, width=80)
            ticker_label.pack(side="left", padx=5)
            
            # Checkbox
            include_var = tk.BooleanVar(value=ticker_settings.get("include", True))
            include_checkbox = ctk.CTkCheckBox(row_frame, text="", variable=include_var, width=20)
            include_checkbox.pack(side="left", padx=5)
            
            # Dropdown
            range_options = ["1 day", "2 days", "3 days", "4 days", "5 days", "7 days", "10 days"]
            range_var = tk.StringVar(value=ticker_settings.get("range", "1 day"))
            range_dropdown = ctk.CTkOptionMenu(
                row_frame,
                variable=range_var,
                values=range_options,
                width=100
            )
            range_dropdown.pack(side="left", padx=5)
            
            # Store references
            ticker_widgets[ticker] = {
                "include_var": include_var,
                "range_var": range_var
            }
        
        # Save button
        def save_settings():
            # Keep window in front
            win.lift()
            win.focus()
            
            new_settings = {}
            for ticker, widgets in ticker_widgets.items():
                new_settings[ticker] = {
                    "include": widgets["include_var"].get(),
                    "range": widgets["range_var"].get()
                }
            set_state_value("group_settings", new_settings)
            print(f"[GROUP SETTINGS] Saved settings: {new_settings}")  # Debug print
            from ui import dialogs
            dialogs.show_timed_message(win, "Settings Saved", "Group settings have been saved.", duration_ms=2000)
            
            # Keep window in front after dialog
            win.after(50, lambda: win.lift())
            win.after(100, lambda: win.focus())
        
        button_frame = ctk.CTkFrame(win, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=10)
        
        save_btn = ctk.CTkButton(button_frame, text="Save Settings", command=save_settings, width=150)
        save_btn.pack(side="left", padx=5)
        
        close_btn = ctk.CTkButton(button_frame, text="Close", command=win.destroy, width=150)
        close_btn.pack(side="left", padx=5)

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
                # Save to JSON config file using the config loader
                from options_dashboard.config_loader import save_api_config, CALLBACK_URL
                success = save_api_config(new_app_key, new_secret, CALLBACK_URL)
                
                if success:
                    dialogs.info("Success", "API credentials saved successfully.\nPlease restart the application for changes to take effect.")
                    win.grab_release()
                    win.destroy()
                else:
                    dialogs.error("Error", "Failed to save credentials to file.")
                
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