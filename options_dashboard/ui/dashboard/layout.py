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

    ctk.CTkButton(
        top,
        text="Fetch All",
        width=120,
        command=self.fetch_all_stocks
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        top,
        text="Edit Tickers",
        width=120,
        command=self.edit_tickers
    ).pack(side="left", padx=10)

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

    ctk.CTkButton(
        self.sidebar,
        text="Generate Chart",
        command=self.generate_selected_chart
    ).pack(fill="x", padx=10, pady=5)

    ctk.CTkButton(
        self.sidebar,
        text="Generate Chart Group",
        command=self.generate_chart_group
    ).pack(fill="x", padx=10, pady=(0, 10))

    # CSV controls
    ctk.CTkLabel(
        self.sidebar,
        text="CSV Index",
        font=ctk.CTkFont(weight="bold")
    ).pack(pady=(10, 5))

    self.csv_symbol_var = tk.StringVar(value="SPX")
    ctk.CTkOptionMenu(
        self.sidebar,
        variable=self.csv_symbol_var,
        values=["SPX", "NDX", "VIX"]
    ).pack(pady=5)

    self.csv_mode_var = tk.StringVar(value="Default File")
    ctk.CTkOptionMenu(
        self.sidebar,
        variable=self.csv_mode_var,
        values=["Default File", "Choose CSV File"]
    ).pack(pady=5)

    ctk.CTkButton(
        self.sidebar,
        text="Load CSV Index",
        command=self.load_csv_index_data
    ).pack(fill="x", padx=10, pady=10)

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
        
        # ---------- Content (tabs) ----------
        self.content = ctk.CTkFrame(self.multi_view, corner_radius=14)
        self.content.pack(fill="both", expand=True)

        apply_ttk_styles()
        build_tabs(self)
    
    # Show multi view
    self.multi_view.pack(fill="both", expand=True)
    
    # Rebuild tabs to show current tickers (if method is available)
    if hasattr(self, 'rebuild_tabs'):
        self.rebuild_tabs()

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
        
        # Use a default symbol or the first preset ticker
        single_symbol = self.preset_tickers[0] if self.preset_tickers else "SPY"
        
        # Create the tab structure directly in single_view (no notebook wrapper)
        tab = ctk.CTkFrame(self.single_view)
        tab.pack(fill="both", expand=True, padx=16, pady=16)
        
        price_var = tk.StringVar(value="—")
        exp_var = tk.StringVar()
        
        # ---------- Header card ----------
        card = ctk.CTkFrame(tab, corner_radius=16)
        card.pack(fill="x", padx=16, pady=16)
        
        ctk.CTkLabel(card, text=single_symbol, font=fonts["lg"]).pack(anchor="w", padx=16, pady=(12, 0))
        
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
            self.on_expiration_change(None, single_symbol)
        
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
        self.ticker_tabs[single_symbol] = {
            "tab": tab,
            "price_var": price_var,
            "exp_var": exp_var,
            "exp_dropdown": exp_dropdown,
            "tree": tree,
            "cols": cols
        }
        
        # Store reference to single view symbol
        self.single_view_symbol = single_symbol
    
    # Show single view
    self.single_view.pack(fill="both", expand=True)
    
    # Update table if data exists
    if hasattr(self, 'single_view_symbol') and self.single_view_symbol in self.ticker_tabs:
        ui = self.ticker_tabs[self.single_view_symbol]
        exp = ui["exp_var"].get()
        if exp:
            self.update_table_for_symbol(self.single_view_symbol, exp)

def toggle_view_mode(self):
    """Toggle between single and multi view - called by switch"""
    # This is handled in the on_toggle callback in build_layout
    pass

def build_tabs(self):
    apply_ttk_styles()

    self.notebook = ttk.Notebook(self.content)
    self.notebook.pack(fill="both", expand=True)
