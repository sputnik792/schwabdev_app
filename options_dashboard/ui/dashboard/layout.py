import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from style.theme import *
from style.ttk_styles import apply_ttk_styles
from style.theme_controller import set_theme_from_switch, is_light_mode, current_icon
from style.tooltip import ToolTip

def build_layout(self):
    fonts = get_fonts()

    # Root container
    self.pack(fill="both", expand=True)

    # ---------- Top bar ----------
    top = ctk.CTkFrame(self, height=56, fg_color=BG_APP)
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

    # ---------- Main ----------
    main = ctk.CTkFrame(self, fg_color=BG_APP)
    main.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ---------- Sidebar ----------
    self.sidebar = ctk.CTkFrame(main, width=260, fg_color=BG_SIDEBAR)
    self.sidebar.pack(side="left", fill="y", padx=(0, 12))
    self.sidebar.pack_propagate(False)

    build_sidebar(self)

    # ---------- Content ----------
    self.content = ctk.CTkFrame(main, fg_color=BG_CONTENT, corner_radius=14)
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

    # Exposure model
    self.model_var = tk.StringVar(value="Gamma")
    ctk.CTkLabel(self.sidebar, text="Exposure Model").pack(pady=(0, 5))
    ctk.CTkSegmentedButton(
        self.sidebar,
        values=["Gamma", "Vanna", "Volga", "Charm"],
        variable=self.model_var
    ).pack(pady=(0, 15))

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

    ctk.CTkFrame(self.sidebar, height=1).pack(fill="x", pady=14)

    # Icon label (dynamic)
    theme_icon = ctk.CTkLabel(
        self.sidebar,
        text=current_icon(),
        font=fonts["lg"],
        text_color=TEXT_SECONDARY
    )
    theme_icon.pack(pady=(0, 6))

    # Theme switch
    theme_switch = ctk.CTkSwitch(
        self.sidebar,
        text="Light Mode",
        font=fonts["md"]
    )

    # Initial state
    if is_light_mode():
        theme_switch.select()
    else:
        theme_switch.deselect()

    def on_theme_toggle():
        is_light = bool(theme_switch.get())
        set_theme_from_switch(is_light)
        theme_icon.configure(text=current_icon())

    theme_switch.configure(command=on_theme_toggle)
    theme_switch.pack(pady=(0, 18))

    # Tooltip
    ToolTip(theme_switch, "Toggle light / dark mode")

def build_tabs(self):
    apply_ttk_styles()

    self.notebook = ttk.Notebook(self.content)
    self.notebook.pack(fill="both", expand=True)
