import tkinter as tk
from tkinter import ttk
from tksheet import Sheet
from style.theme import *
from style.theme import get_fonts
import customtkinter as ctk

def rebuild_tabs(self):
    for tab in self.notebook.tabs():
        self.notebook.forget(tab)

    # Preserve single view entries when rebuilding tabs
    # Single view entries use keys starting with "_single_" or "_SINGLE_VIEW_PLACEHOLDER"
    single_view_entries = {}
    for key, value in self.ticker_tabs.items():
        if key.startswith("_single_") or key == "_SINGLE_VIEW_PLACEHOLDER":
            single_view_entries[key] = value
    
    self.ticker_tabs.clear()
    
    # Restore single view entries
    self.ticker_tabs.update(single_view_entries)
    
    for symbol in self.preset_tickers:
        create_stock_tab(self, symbol)

def create_stock_tab(self, symbol):
    fonts = get_fonts()

    tab = ctk.CTkFrame(self.notebook)
    self.notebook.add(tab, text=symbol)

    price_var = tk.StringVar(value="—")
    exp_var = tk.StringVar()

    # ---------- Header card ----------
    card = ctk.CTkFrame(tab, corner_radius=16)
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
    
    def on_expiration_selected(selected_value):
        exp_var.set(selected_value)
        self.on_expiration_change(None, symbol)
    
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
    
    # Create tksheet instead of Treeview
    sheet = Sheet(
        table_wrap,
        data=[],  # Start with empty data
        headers=headers,
        show_row_index=False,
        show_top_left=False,
        empty_horizontal=0,
        empty_vertical=0
    )
    # Set larger font size for better readability
    sheet.font(newfont=("Segoe UI", 12, "normal"))
    sheet.enable_bindings("all")
    sheet.pack(fill="both", expand=True)

    self.ticker_tabs[symbol] = {
        "tab": tab,
        "price_var": price_var,
        "exp_var": exp_var,
        "exp_dropdown": exp_dropdown,
        "sheet": sheet,
        "cols": cols,
        "headers": headers
    }

def update_table_for_symbol(self, symbol, expiration):
    ui = self.ticker_tabs.get(symbol)
    if not ui:
        return
    sheet = ui.get("sheet")
    cols = ui.get("cols")
    if not sheet or not cols:
        # Sheet not found - this shouldn't happen but handle gracefully
        return
    
    state = self.ticker_data.get(symbol)
    if not state:
        return
    df = state.exp_data_map.get(expiration)
    if df is None or df.empty:
        # Clear the sheet if no data
        sheet.set_sheet_data([])
        return

    # Convert DataFrame to list of lists for tksheet
    data = []
    for _, row in df.iterrows():
        data.append([str(row.get(c, "")) for c in cols])
    
    # Update the sheet with new data
    sheet.set_sheet_data(data)

def on_expiration_change(self, event, symbol):
    ui = self.ticker_tabs.get(symbol)
    if not ui:
        return
    self.update_table_for_symbol(symbol, ui["exp_var"].get())