import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from style.theme import *
from style.ttk_styles import apply_ttk_styles
from style.theme_controller import set_theme_from_switch, is_light_mode, current_icon
from style.tooltip import ToolTip
from style.custom_theme_controller import list_available_themes, set_color_theme, get_current_theme
from state.app_state import get_state_value, set_state_value

def build_layout(self):
    fonts = get_fonts()

    # Root container
    self.pack(fill="both", expand=True)

    # ---------- Top bar ----------
    top = ctk.CTkFrame(self, height=56)
    top.pack(fill="x", padx=12, pady=10)

    ctk.CTkLabel(
        top,
        text="Options Dashboard",
        font=fonts["lg"]
    ).pack(side="left", padx=12)

    # View mode toggle - load from app_state
    saved_view_mode = get_state_value("view_mode", "multi")
    if not hasattr(self, 'view_mode'):
        self.view_mode = tk.StringVar(value=saved_view_mode)
    
    toggle_frame = ctk.CTkFrame(top, fg_color="transparent")
    toggle_frame.pack(side="left", padx=10)
    
    ctk.CTkLabel(toggle_frame, text="Single", font=fonts["sm"]).pack(side="left", padx=(0, 5))
    
    def on_toggle():
        if hasattr(self, 'view_toggle'):
            if self.view_toggle.get():  # Selected = multi
                self.view_mode.set("multi")
                set_state_value("view_mode", "multi")
                if hasattr(self, 'show_multi_view'):
                    self.show_multi_view()
            else:  # Unselected = single
                self.view_mode.set("single")
                set_state_value("view_mode", "single")
                if hasattr(self, 'show_single_view'):
                    self.show_single_view()
    
    self.view_toggle = ctk.CTkSwitch(
        toggle_frame,
        text="",
        command=on_toggle,
        width=50
    )
    self.view_toggle.pack(side="left")
    # Selected = multi mode, Unselected = single mode
    if self.view_mode.get() == "multi":
        self.view_toggle.select()
    ctk.CTkLabel(toggle_frame, text="Multi", font=fonts["sm"]).pack(side="left", padx=(5, 0))

    # ---------- Main ----------
    self.main = ctk.CTkFrame(self)
    self.main.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ---------- Sidebar (Global - always visible) ----------
    self.sidebar_container = ctk.CTkFrame(self.main, width=260)
    self.sidebar_container.pack(side="left", fill="y", padx=(0, 12))
    self.sidebar_container.pack_propagate(False)
    
    # Create scrollable sidebar
    self.sidebar = ctk.CTkScrollableFrame(self.sidebar_container, width=240)
    self.sidebar.pack(fill="both", expand=True, padx=10, pady=10)
    
    build_sidebar(self)

    # ---------- Content area (switches between views) ----------
    self.content_area = ctk.CTkFrame(self.main)
    self.content_area.pack(side="left", fill="both", expand=True)

    # Store view containers
    self.multi_view = None
    self.single_view = None
    
    # View will be initialized after methods are bound in dashboard.py

def build_sidebar(self):
    fonts = get_fonts()

    ctk.CTkLabel(
        self.sidebar,
        text="Controls",
        font=ctk.CTkFont(size=19, weight="bold")
    ).pack(pady=(10, 8))

    # Chart output
    self.chart_output_var = tk.StringVar(value="Desktop")
    ctk.CTkLabel(self.sidebar, text="Chart Output").pack(pady=(0, 5))
    ctk.CTkOptionMenu(
        self.sidebar,
        variable=self.chart_output_var,
        values=["Browser", "Desktop"],
        width=160
    ).pack(pady=(0, 15))

    ctk.CTkButton(
        self.sidebar,
        text="Stats Breakdown",
        command=self.open_stats
    ).pack(fill="x", padx=10, pady=6)

    # Exposure model
    default_model = get_state_value("exposure_model", "Gamma")
    self.model_var = tk.StringVar(value=default_model)
    
    def on_model_change(value):
        set_state_value("exposure_model", value)
    
    ctk.CTkLabel(self.sidebar, text="Exposure Model").pack(pady=(0, 5))
    model_button = ctk.CTkSegmentedButton(
        self.sidebar,
        values=["Gamma", "Vanna", "Volga", "Charm"],
        variable=self.model_var,
        command=on_model_change
    )
    model_button.pack(pady=(0, 15))

    ctk.CTkFrame(self.sidebar, height=1).pack(fill="x", pady=5)
    # ----------------------------------
    # Color Theme Selector
    # ----------------------------------

    ctk.CTkLabel(
        self.sidebar,
        text="Color Theme",
        font=fonts["md"]
    ).pack(pady=(10, 5))

    themes = list_available_themes()

    # Load theme from state or current theme, default to first available
    saved_theme = get_state_value("color_theme")
    current_theme = get_current_theme() or saved_theme
    theme_value = current_theme or (themes[0] if themes else "")
    
    self.color_theme_var = ctk.StringVar(value=theme_value)

    def on_theme_change(theme_name: str):
        if theme_name:
            set_color_theme(theme_name)
            set_state_value("color_theme", theme_name)

    theme_dropdown = ctk.CTkOptionMenu(
        self.sidebar,
        values=themes,
        variable=self.color_theme_var,
        command=on_theme_change,
        width=160
    )

    theme_dropdown.pack(pady=(0, 12))

    ctk.CTkFrame(self.sidebar, height=1).pack(fill="x", pady=5)

    # Icon label (dynamic)
    theme_icon = ctk.CTkLabel(
        self.sidebar,
        text=current_icon(),
        font=fonts["lg"],
        text_color=TEXT_SECONDARY
    )
    theme_icon.pack(pady=(0, 6))

    # Theme switch (text will be set dynamically)
    theme_switch = ctk.CTkSwitch(
        self.sidebar,
        font=fonts["md"]
    )

    # Initial state + label
    if is_light_mode():
        theme_switch.select()
        theme_switch.configure(text="Switch to\nDark Mode")
    else:
        theme_switch.deselect()
        theme_switch.configure(text="Switch to\nLight Mode")

    def on_theme_toggle():
        is_light = bool(theme_switch.get())
        set_theme_from_switch(is_light)

        # Update icon
        theme_icon.configure(text=current_icon())

        # Update label text
        theme_switch.configure(
            text="Switch to\nDark Mode" if is_light else "Switch to\nLight Mode"
        )

    theme_switch.configure(command=on_theme_toggle)
    theme_switch.pack(pady=(0, 18))
    # Tooltip
    ToolTip(theme_switch, "Toggle light / dark mode")
    
    # Separator
    ctk.CTkFrame(self.sidebar, height=1).pack(fill="x", pady=5)
    
    # API Credentials button
    ctk.CTkButton(
        self.sidebar,
        text="API Credentials",
        command=self.edit_api_credentials
    ).pack(fill="x", padx=10, pady=10)

def show_multi_view(self):
    """Show the multi-tab view"""
    # Hide single view if it exists
    if self.single_view:
        self.single_view.pack_forget()
        # Clean up single view ticker from ticker_tabs if it exists
        if hasattr(self, 'single_view_symbol') and self.single_view_symbol in self.ticker_tabs:
            # Don't delete the data, just remove the UI reference
            # The data will be reused if the ticker is in preset_tickers
            pass
    
    # Create multi view if it doesn't exist
    if not self.multi_view:
        self.multi_view = ctk.CTkFrame(self.content_area, corner_radius=14)
        
        # ---------- Button bar above tabs ----------
        button_bar = ctk.CTkFrame(self.multi_view, fg_color="transparent")
        button_bar.pack(fill="x", padx=16, pady=(16, 8))
        
        ctk.CTkButton(
            button_bar,
            text="Fetch All",
            width=120,
            command=self.fetch_all_stocks
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            button_bar,
            text="Edit Tickers",
            width=120,
            command=self.edit_tickers
        ).pack(side="left", padx=10)
        
        # Store reference to chart group button so we can enable/disable it
        self.generate_chart_group_button = ctk.CTkButton(
            button_bar,
            text="Generate Chart Group",
            width=150,
            command=self.generate_chart_group,
            state="disabled"  # Disabled until fetch all completes
        )
        self.generate_chart_group_button.pack(side="left", padx=10)
        
        # ---------- Content (tabs) ----------
        self.content = ctk.CTkFrame(self.multi_view, corner_radius=14)
        self.content.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        apply_ttk_styles()
        build_tabs(self)
    
    # Show multi view
    self.multi_view.pack(fill="both", expand=True)
    
    # Rebuild tabs to show current tickers (if method is available)
    if hasattr(self, 'rebuild_tabs'):
        self.rebuild_tabs()
    
    # Repopulate tables and prices for tickers that already have data
    # This ensures data persists when switching back from single view
    for symbol in self.preset_tickers:
        if symbol in self.ticker_data and symbol in self.ticker_tabs:
            state = self.ticker_data[symbol]
            ui = self.ticker_tabs[symbol]
            
            # Update price
            if state.price > 0:
                ui["price_var"].set(f"${state.price:.2f}")
            
            # Update expiration dropdown and table if data exists
            if state.exp_data_map:
                expirations = list(state.exp_data_map.keys())
                if expirations:
                    # Sort expirations (they should already be normalized)
                    expirations.sort()
                    ui["exp_dropdown"].configure(values=expirations)
                    
                    # Set expiration (use existing if available, otherwise first)
                    current_exp = ui["exp_var"].get()
                    if current_exp and current_exp in expirations:
                        ui["exp_var"].set(current_exp)
                    else:
                        ui["exp_var"].set(expirations[0])
                    
                    # Repopulate table with data
                    self.update_table_for_symbol(symbol, ui["exp_var"].get())

def show_single_view(self):
    """Show the single ticker view"""
    # Hide multi view if it exists
    if self.multi_view:
        self.multi_view.pack_forget()
    
    # Create single view if it doesn't exist
    if not self.single_view:
        self.single_view = ctk.CTkFrame(self.content_area, corner_radius=14)
        
        # Apply styles for ttk widgets
        apply_ttk_styles()
        
        # Create single ticker panel (similar to create_stock_tab but without notebook)
        from ui.dashboard.tabs import create_stock_tab
        from style.theme import get_fonts
        
        fonts = get_fonts()
        
        # Use a default symbol - but don't use one that might have multi-view data
        # Use a placeholder that won't conflict
        single_symbol = "_SINGLE_VIEW_PLACEHOLDER"
        
        # Create the tab structure directly in single_view (no notebook wrapper)
        tab = ctk.CTkFrame(self.single_view)
        tab.pack(fill="both", expand=True, padx=16, pady=16)
        
        price_var = tk.StringVar(value="—")
        exp_var = tk.StringVar()
        ticker_var = tk.StringVar(value="")  # Start empty, user must enter ticker
        
        # ---------- Header row (card on left, ticker input in middle, CSV controls on right) ----------
        header_row = ctk.CTkFrame(tab, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=16)
        
        # Header card (left side)
        card = ctk.CTkFrame(header_row, corner_radius=16)
        card.pack(side="left", fill="both", expand=True, padx=(0, 16))
        
        # Ticker label (will be updated when ticker changes)
        # Use a separate variable for display that starts empty
        ticker_display_var = tk.StringVar(value="")
        ticker_label = ctk.CTkLabel(card, textvariable=ticker_display_var, font=fonts["lg"])
        ticker_label.pack(anchor="w", padx=16, pady=(12, 0))
        
        ctk.CTkLabel(
            card,
            textvariable=price_var,
            font=fonts["xxl"],
            text_color=ACCENT_PRIMARY
        ).pack(anchor="w", padx=16)
        
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(anchor="w", padx=16, pady=(6, 12))
        
        ctk.CTkLabel(row, text="Expiration:", font=fonts["md"], text_color=TEXT_MUTED).pack(side="left")
        
        def on_expiration_selected(selected_value):
            exp_var.set(selected_value)
            # Use current ticker from ticker_var instead of hardcoded single_symbol
            current_ticker = ticker_var.get().strip().upper()
            if current_ticker:
                self.on_expiration_change(None, current_ticker)
        
        exp_dropdown = ctk.CTkOptionMenu(
            row,
            variable=exp_var,
            values=[],  # Will be populated when data is loaded
            command=on_expiration_selected,
            width=300,
            font=ctk.CTkFont(size=14),
            dropdown_font=ctk.CTkFont(size=16),
            height=36
        )
        exp_dropdown.pack(side="left", padx=8)
        
        # Generate Chart button below expiration dropdown
        chart_button_row = ctk.CTkFrame(card, fg_color="transparent")
        chart_button_row.pack(anchor="w", padx=16, pady=(0, 12))
        
        # Store reference to generate chart button so we can enable/disable it
        self.generate_chart_button = ctk.CTkButton(
            chart_button_row,
            text="Generate Chart",
            command=self.generate_selected_chart,
            width=150,
            state="disabled"  # Disabled until fetch completes
        )
        self.generate_chart_button.pack(side="left")
        
        # Ticker input panel (middle section)
        ticker_panel = ctk.CTkFrame(header_row, corner_radius=16)
        ticker_panel.pack(side="left", fill="y", padx=(0, 16))
        
        ctk.CTkLabel(
            ticker_panel,
            text="Ticker Symbol",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(16, 10), padx=16)
        
        ticker_entry = ctk.CTkEntry(
            ticker_panel,
            textvariable=ticker_var,
            width=150,
            font=ctk.CTkFont(size=14),
            height=36
        )
        ticker_entry.pack(pady=5, padx=16)
        
        # Container for autocomplete suggestions (will be shown/hidden dynamically)
        autocomplete_container = ctk.CTkFrame(ticker_panel, fg_color="transparent")
        # Don't pack initially - will be packed when suggestions appear
        
        # Initialize autocomplete feature
        from ml_features.ticker_autocomplete import TickerAutocomplete
        
        def on_ticker_selected(ticker):
            # When a ticker is selected, hide suggestions
            autocomplete_container.pack_forget()
        
        autocomplete = TickerAutocomplete(
            ticker_panel,  # Parent for positioning
            ticker_entry,
            max_suggestions=5,
            on_selection=on_ticker_selected
        )
        
        # Store autocomplete reference
        self.single_view_autocomplete = autocomplete
        self.single_view_autocomplete_container = autocomplete_container
        
        # Override the _show_suggestions to position in container instead of absolute place()
        original_show = autocomplete._show_suggestions
        def custom_show_suggestions(matches):
            if not matches:
                autocomplete_container.pack_forget()
                if autocomplete.suggestion_frame:
                    autocomplete.suggestion_frame.destroy()
                    autocomplete.suggestion_frame = None
                return
            
            # Show container between entry and button (before fetch button)
            if hasattr(self, 'single_view_fetch_button'):
                autocomplete_container.pack(pady=(0, 5), padx=16, fill="x", before=self.single_view_fetch_button)
            else:
                autocomplete_container.pack(pady=(0, 5), padx=16, fill="x")
            
            # Clear existing suggestions in container
            for widget in autocomplete_container.winfo_children():
                widget.destroy()
            
            # Create suggestion buttons in container
            for ticker in matches[:5]:  # Limit to 5
                btn = ctk.CTkButton(
                    autocomplete_container,
                    text=ticker,
                    command=lambda t=ticker: autocomplete._select_ticker(t),
                    width=150,
                    height=28,
                    font=ctk.CTkFont(size=12),
                    fg_color=("gray75", "gray25"),
                    hover_color=("gray65", "gray35")
                )
                btn.pack(pady=2, fill="x")
            
            autocomplete.is_visible = True
        
        autocomplete._show_suggestions = custom_show_suggestions
        
        # Override _hide_suggestions to also hide container
        original_hide = autocomplete._hide_suggestions
        def custom_hide_suggestions(event=None):
            original_hide()
            autocomplete_container.pack_forget()
        
        autocomplete._hide_suggestions = custom_hide_suggestions
        
        # Also hide on key release if entry is empty
        original_on_key_release = autocomplete._on_key_release
        def on_key_release(event):
            value = ticker_var.get().strip()
            if not value:
                autocomplete_container.pack_forget()
            # Call original handler
            original_on_key_release(event)
        
        ticker_entry.unbind("<KeyRelease>")
        ticker_entry.bind("<KeyRelease>", on_key_release)
        
        def fetch_single_ticker_data():
            symbol = ticker_var.get().strip().upper()
            if not symbol:
                from ui import dialogs
                dialogs.warning("Invalid Ticker", "Please enter a ticker symbol.")
                return
            
            # Disable Generate Chart button when starting a new fetch
            if hasattr(self, 'generate_chart_button'):
                self.generate_chart_button.configure(state="disabled")
            
            # Fetch data for this ticker
            from ui.dashboard.data_controller import fetch_single_symbol_for_view
            fetch_single_symbol_for_view(self, symbol, ticker_var, price_var, exp_var, exp_dropdown, ticker_label)
        
        fetch_button = ctk.CTkButton(
            ticker_panel,
            text="Fetch Options Data",
            command=fetch_single_ticker_data,
            width=150
        )
        fetch_button.pack(pady=(5, 16), padx=16)
        
        # Store button reference for positioning autocomplete before it
        self.single_view_fetch_button = fetch_button
        
        # CSV controls (right side)
        csv_panel = ctk.CTkFrame(header_row, corner_radius=16)
        csv_panel.pack(side="right", fill="y")
        
        ctk.CTkLabel(
            csv_panel,
            text="CSV Index",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(16, 10), padx=16)
        
        # Use existing CSV variables (initialized in dashboard.py)
        ctk.CTkOptionMenu(
            csv_panel,
            variable=self.csv_symbol_var,
            values=["SPX", "NDX", "VIX"],
            width=150
        ).pack(pady=5, padx=16)
        
        ctk.CTkOptionMenu(
            csv_panel,
            variable=self.csv_mode_var,
            values=["Default File", "Choose CSV File"],
            width=150
        ).pack(pady=5, padx=16)
        
        ctk.CTkButton(
            csv_panel,
            text="Load CSV Index",
            command=self.load_csv_index_data,
            width=150
        ).pack(pady=(5, 16), padx=16)
        
        # ---------- Table ----------
        table_wrap = ctk.CTkFrame(tab, corner_radius=14)
        table_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        cols = [
            "Bid_Call","Ask_Call","Delta_Call","Theta_Call","Gamma_Call","IV_Call","OI_Call",
            "Strike",
            "Bid_Put","Ask_Put","Delta_Put","Theta_Put","Gamma_Put","IV_Put","OI_Put"
        ]
        headers = [
            "Call Bid","Call Ask","Δ(Call)","Θ(Call)","Γ(Call)","IV(Call)","OI(Call)",
            "Strike",
            "Put Bid","Put Ask","Δ(Put)","Θ(Put)","Γ(Put)","IV(Put)","OI(Put)"
        ]
        
        tree = ttk.Treeview(table_wrap, columns=cols, show="headings")
        
        for c, h in zip(cols, headers):
            tree.heading(c, text=h)
            tree.column(c, width=110, anchor="center")
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=tree.xview)
        
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)
        
        # Store in ticker_tabs dict so it works with existing update mechanisms
        # Use a special key for single view to avoid conflicts with multi-view entries
        # Single view entries are identified by having "ticker_var" key
        # If an entry already exists for this symbol from multi-view, create a new one for single view
        # We'll use the symbol as the key, but ensure we don't overwrite multi-view entries
        if single_symbol in self.ticker_tabs:
            # Check if this is a multi-view entry (has "tab" that's a notebook tab, not a CTkFrame)
            existing_entry = self.ticker_tabs[single_symbol]
            # Multi-view entries don't have "ticker_var", single view entries do
            if "ticker_var" not in existing_entry:
                # This is a multi-view entry, create a new entry for single view
                # We'll use a special marker to indicate this is single view
                pass  # Continue to create new entry below
        
        # Create/update entry for single view
        self.ticker_tabs[single_symbol] = {
            "tab": tab,
            "price_var": price_var,
            "exp_var": exp_var,
            "exp_dropdown": exp_dropdown,
            "tree": tree,
            "cols": cols,
            "ticker_var": ticker_var,
            "ticker_label": ticker_label,
            "_is_single_view": True  # Marker to identify single view entries
        }
        
        # Store reference to single view symbol and UI components
        self.single_view_symbol = single_symbol
        self.single_view_ticker_var = ticker_var
        self.single_view_ticker_display_var = ticker_display_var  # Separate display variable
        self.single_view_price_var = price_var
        self.single_view_exp_var = exp_var
        self.single_view_exp_dropdown = exp_dropdown
        self.single_view_ticker_label = ticker_label
    
    # Show single view
    self.single_view.pack(fill="both", expand=True)
    
    # Single view should be independent - don't auto-populate from multi-view data
    # Only show data that was explicitly fetched in single view
    # When switching to single view, clear it unless it has its own data
    if hasattr(self, 'single_view_symbol') and self.single_view_symbol in self.ticker_tabs:
        symbol = self.single_view_symbol
        ui = self.ticker_tabs[symbol]
        
        # Verify this is a single view entry (has _is_single_view marker or ticker_var)
        is_single_view_entry = ui.get("_is_single_view") or "ticker_var" in ui
        
        if not is_single_view_entry:
            # This is a multi-view entry, don't use it - single view should be independent
            # Clear the display
            if hasattr(self, 'single_view_ticker_display_var'):
                self.single_view_ticker_display_var.set("")
            if hasattr(self, 'single_view_price_var'):
                self.single_view_price_var.set("—")
            if hasattr(self, 'single_view_exp_var'):
                self.single_view_exp_var.set("")
            if hasattr(self, 'single_view_exp_dropdown'):
                self.single_view_exp_dropdown.configure(values=[])
            # Clear the table
            if ui.get("tree"):
                ui["tree"].delete(*ui["tree"].get_children())
            return
        
        # Single view should NOT auto-populate from ticker_data
        # Only show data that was explicitly fetched in single view
        # When switching to single view, clear it unless it has its own fetched data
        # We'll track this by checking if single_view_symbol matches and if data was fetched via single view
        # For now, just clear single view when switching to it - user must fetch data explicitly
        # Clear the display to ensure independence
        if hasattr(self, 'single_view_ticker_display_var'):
            self.single_view_ticker_display_var.set("")
        if hasattr(self, 'single_view_price_var'):
            self.single_view_price_var.set("—")
        if hasattr(self, 'single_view_exp_var'):
            self.single_view_exp_var.set("")
        if hasattr(self, 'single_view_exp_dropdown'):
            self.single_view_exp_dropdown.configure(values=[])
        # Clear the table
        if ui.get("tree"):
            ui["tree"].delete(*ui["tree"].get_children())
        
        # Only repopulate if this symbol was explicitly fetched in single view
        # We can't perfectly track this, so we'll just not auto-populate
        # The user must fetch data explicitly in single view
        return
        
        # (Code below is unreachable but kept for reference)
        if symbol in self.ticker_data and ui.get("price_var") == self.single_view_price_var:
            state = self.ticker_data[symbol]
            
            # Update price display
            if state.price > 0:
                ui["price_var"].set(f"${state.price:.2f}")
                if hasattr(self, 'single_view_price_var'):
                    self.single_view_price_var.set(f"${state.price:.2f}")
            
            # Update ticker display label
            if hasattr(self, 'single_view_ticker_display_var'):
                self.single_view_ticker_display_var.set(symbol)
            if hasattr(self, 'single_view_ticker_label'):
                self.single_view_ticker_label.configure(text=symbol)
            
            # Update ticker input field
            if hasattr(self, 'single_view_ticker_var'):
                self.single_view_ticker_var.set(symbol)
            
            # Update expiration dropdown and table if data exists
            if state.exp_data_map:
                expirations = list(state.exp_data_map.keys())
                if expirations:
                    # Sort expirations
                    expirations.sort()
                    ui["exp_dropdown"].configure(values=expirations)
                    
                    # Set expiration (use existing if available, otherwise first)
                    current_exp = ui["exp_var"].get()
                    if current_exp and current_exp in expirations:
                        ui["exp_var"].set(current_exp)
                    else:
                        ui["exp_var"].set(expirations[0])
                    
                    # Repopulate table with cached data
                    self.update_table_for_symbol(symbol, ui["exp_var"].get())
                    
                    # Enable Generate Chart button since we have data
                    if hasattr(self, 'generate_chart_button'):
                        self.generate_chart_button.configure(state="normal")

def toggle_view_mode(self):
    """Toggle between single and multi view - called by switch"""
    # This is handled in the on_toggle callback in build_layout
    pass

def build_tabs(self):
    apply_ttk_styles()

    self.notebook = ttk.Notebook(self.content)
    self.notebook.pack(fill="both", expand=True)
