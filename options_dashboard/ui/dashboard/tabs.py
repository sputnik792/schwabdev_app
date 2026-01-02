import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

def rebuild_tabs(self):
    for tab in self.notebook.tabs():
        self.notebook.forget(tab)

    self.ticker_tabs.clear()

    for symbol in self.preset_tickers:
        create_stock_tab(self, symbol)

def create_stock_tab(self, symbol):
    tab = ctk.CTkFrame(self.notebook)
    self.notebook.add(tab, text=symbol)

    price_var = tk.StringVar(value="—")
    exp_var = tk.StringVar()

    header = ctk.CTkFrame(tab)
    header.pack(fill="x", pady=5, padx=5)

    ctk.CTkLabel(header, text=f"{symbol} Price:").pack(side="left")
    ctk.CTkLabel(
        header,
        textvariable=price_var,
        font=ctk.CTkFont(weight="bold")
    ).pack(side="left", padx=10)

    ctk.CTkLabel(header, text="Expiration:").pack(side="left")
    exp_dropdown = ttk.Combobox(
        header,
        textvariable=exp_var,
        state="readonly",
        width=25
    )
    exp_dropdown.pack(side="left", padx=5)
    exp_dropdown.bind(
        "<<ComboboxSelected>>",
        lambda e, s=symbol: on_expiration_change(self, e, s)
    )

    frame = ctk.CTkFrame(tab)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    cols = [
        "Bid_Call", "Ask_Call", "Delta_Call", "Theta_Call",
        "Gamma_Call", "IV_Call", "OI_Call",
        "Strike",
        "Bid_Put", "Ask_Put", "Delta_Put", "Theta_Put",
        "Gamma_Put", "IV_Put", "OI_Put"
    ]

    tree = ttk.Treeview(frame, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c.replace("_", " "))
        tree.column(c, width=95, anchor="center")

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscroll=vsb.set)

    vsb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    self.ticker_tabs[symbol] = {
        "tab": tab,
        "price_var": price_var,
        "exp_var": exp_var,
        "exp_dropdown": exp_dropdown,
        "tree": tree,
        "cols": cols
    }

def update_table_for_symbol(self, symbol, expiration):
    ui = self.ticker_tabs.get(symbol)
    if not ui:
        return
    tree = ui["tree"]
    cols = ui["cols"]
    tree.delete(*tree.get_children())
    df = self.ticker_data.get(symbol, {}).exp_data_map.get(expiration)
    if df is None:
        return

    for _, row in df.iterrows():
        tree.insert("", tk.END, values=[row.get(c, "") for c in cols])

def on_expiration_change(self, event, symbol):
    ui = self.ticker_tabs.get(symbol)
    if not ui:
        return
    update_table_for_symbol(self, symbol, ui["exp_var"].get())
