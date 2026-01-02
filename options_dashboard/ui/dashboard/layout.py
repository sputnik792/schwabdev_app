import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

def build_layout(self):
    # ---------- Top Bar ----------
    self.top_bar = ctk.CTkFrame(self, height=48)
    self.top_bar.pack(side="top", fill="x", padx=10, pady=(10, 5))

    ctk.CTkButton(
        self.top_bar,
        text="Fetch All",
        width=120,
        command=self.fetch_all_stocks
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        self.top_bar,
        text="Edit Preset Tickers",
        width=180,
        command=self.edit_tickers
    ).pack(side="left", padx=5)

    # ---------- Main Area ----------
    self.main = ctk.CTkFrame(self)
    self.main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ---------- Sidebar ----------
    self.sidebar = ctk.CTkFrame(self.main, width=220)
    self.sidebar.pack(side="left", fill="y", padx=(0, 10), pady=5)
    self.sidebar.pack_propagate(False)

    build_sidebar(self)

    # ---------- Content ----------
    self.content = ctk.CTkFrame(self.main)
    self.content.pack(side="left", fill="both", expand=True, pady=5)

    build_tabs(self)


def build_sidebar(self):
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


def build_tabs(self):
    style = ttk.Style()
    style.theme_use("default")

    self.notebook = ttk.Notebook(self.content)
    self.notebook.pack(fill="both", expand=True)
