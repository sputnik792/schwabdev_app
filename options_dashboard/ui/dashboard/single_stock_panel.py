import customtkinter as ctk
import tkinter as tk

from ui.dashboard.data_controller import (
    fetch_single_symbol,
    load_csv_index_data
)

def build_single_stock_panel(self):
    panel = ctk.CTkFrame(self)
    panel.pack(fill="x", padx=12, pady=8)

    self.single_symbol_var = tk.StringVar(value="SPY")

    ctk.CTkEntry(
        panel,
        textvariable=self.single_symbol_var,
        width=120
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        panel,
        text="Fetch Option",
        command=lambda: fetch_single_symbol(
            self, self.single_symbol_var.get()
        )
    ).pack(side="left", padx=5)

    ctk.CTkLabel(panel, text="Index").pack(side="left", padx=(20, 5))

    self.csv_symbol_var = tk.StringVar(value="SPX")
    ctk.CTkOptionMenu(
        panel,
        values=["SPX", "NDX", "VIX"],
        variable=self.csv_symbol_var
    ).pack(side="left", padx=5)

    ctk.CTkButton(
        panel,
        text="Load CSV",
        command=lambda: load_csv_index_data(
            self,
            self.csv_symbol_var.get(),
            "Default File"
        )
    ).pack(side="left", padx=5)
