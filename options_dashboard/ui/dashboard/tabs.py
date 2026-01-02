import tkinter as tk
from tkinter import ttk
from style.theme import *
from style.theme import get_fonts
import customtkinter as ctk

def rebuild_tabs(self):
    for tab in self.notebook.tabs():
        self.notebook.forget(tab)

    self.ticker_tabs.clear()
    for symbol in self.preset_tickers:
        create_stock_tab(self, symbol)

def create_stock_tab(self, symbol):
    fonts = get_fonts()

    tab = ctk.CTkFrame(self.notebook, fg_color=BG_CONTENT)
    self.notebook.add(tab, text=symbol)

    price_var = tk.StringVar(value="—")
    exp_var = tk.StringVar()

    # ---------- Header card ----------
    card = ctk.CTkFrame(tab, fg_color=CARD_BG, corner_radius=16)
    card.pack(fill="x", padx=16, pady=16)

    ctk.CTkLabel(card, text=symbol, font=fonts["lg"]).pack(anchor="w", padx=16, pady=(12, 0))

    ctk.CTkLabel(
        card,
        textvariable=price_var,
        font=fonts["xxl"],
        text_color=ACCENT_PRIMARY
    ).pack(anchor="w", padx=16)

    row = ctk.CTkFrame(card, fg_color="transparent")
    row.pack(anchor="w", padx=16, pady=(6, 12))

    ctk.CTkLabel(row, text="Expiration:", font=fonts["md"], text_color=TEXT_MUTED).pack(side="left")
    exp_dropdown = ttk.Combobox(row, textvariable=exp_var, state="readonly", width=26)
    exp_dropdown.pack(side="left", padx=8)

    exp_dropdown.bind("<<ComboboxSelected>>", lambda e, s=symbol: self.on_expiration_change(e, s))

    # ---------- Table ----------
    table_wrap = ctk.CTkFrame(tab, fg_color=TABLE_BG, corner_radius=14)
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
    state = self.ticker_data.get(symbol)
    if not state:
        return
    df = state.exp_data_map.get(expiration)
    if df is None or df.empty:
        return

    for _, row in df.iterrows():
        tree.insert(
            "",
            tk.END,
            values=[row.get(c, "") for c in cols]
        )

def on_expiration_change(self, event, symbol):
    ui = self.ticker_tabs.get(symbol)
    if not ui:
        return
    self.update_table_for_symbol(symbol, ui["exp_var"].get())