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
    main = ctk.CTkFrame(self)
    main.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ---------- Sidebar ----------
    self.sidebar = ctk.CTkFrame(main, width=260)
    self.sidebar.pack(side="left", fill="y", padx=(0, 12))
    self.sidebar.pack_propagate(False)

    build_sidebar(self)

    # ---------- Content ----------
    self.content = ctk.CTkFrame(main, corner_radius=14)
    self.content.pack(side="left", fill="both", expand=True)

    apply_ttk_styles()
    build_tabs(self)

def build_sidebar(self):
    fonts = get_fonts()

    ctk.CTkLabel(
        self.sidebar,
        text="Controls",
        font=ctk.CTkFont(size=16, weight="bold")
    ).pack(pady=(10, 15))

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
    ).pack(fill="x", padx=10, pady=(0, 15))

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

def build_tabs(self):
    apply_ttk_styles()

    self.notebook = ttk.Notebook(self.content)
    self.notebook.pack(fill="both", expand=True)
