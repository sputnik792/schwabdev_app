import tkinter as tk
from tkinter import ttk
from tksheet import Sheet
from style.theme import *
import customtkinter as ctk
import pandas as pd

def reapply_highlighting_for_symbol(dashboard, symbol):
    """
    Re-apply highlighting for a symbol when price changes
    Works for both single-view and multi-view
    """
    state = dashboard.ticker_data.get(symbol)
    if not state or not state.exp_data_map:
        return
    
    # Try multi-view first
    ui = dashboard.ticker_tabs.get(symbol)
    if ui and not ui.get("_is_single_view"):
        sheet = ui.get("sheet")
        cols = ui.get("cols")
        exp_var = ui.get("exp_var")
        if sheet and cols and exp_var:
            expiration = exp_var.get()
            if expiration and expiration in state.exp_data_map:
                df = state.exp_data_map.get(expiration)
                if df is not None and not df.empty:
                    highlight_rows_by_strike(sheet, df, cols, state.price)
        return
    
    # Try single-view
    single_key = f"_single_{symbol}"
    ui = dashboard.ticker_tabs.get(single_key)
    if ui and ui.get("_is_single_view"):
        sheet = ui.get("sheet")
        cols = ui.get("cols")
        exp_var = ui.get("exp_var")
        if sheet and cols and exp_var:
            expiration = exp_var.get()
            if expiration and expiration in state.exp_data_map:
                df = state.exp_data_map.get(expiration)
                if df is not None and not df.empty:
                    highlight_rows_by_strike(sheet, df, cols, state.price)

def format_row_data(row, cols):
    """
    Format a DataFrame row for display in tksheet.
    Formats Prob ITM columns as percentages.
    """
    row_data = []
    for c in cols:
        val = row.get(c, "")
        # Format Prob ITM columns as percentages
        if c in ["Prob_ITM_Call", "Prob_ITM_Put"]:
            try:
                if pd.notna(val) and val != "":
                    val = f"{float(val) * 100:.2f}%"
                else:
                    val = ""
            except (ValueError, TypeError):
                val = ""
        else:
            val = str(val) if val != "" else ""
        row_data.append(val)
    return row_data

def highlight_rows_by_strike(sheet, df, cols, stock_price):
    """
    Highlight rows in the sheet based on strike price vs stock price
    - Strike <= stock_price: light red (#ffcccc) on columns with "put" in name
    - Strike > stock_price: light green (#ccffcc) on columns with "call" in name
    """
    if not sheet or df is None or df.empty or stock_price <= 0:
        return
    
    # Find the Strike column index
    try:
        strike_col_idx = cols.index("Strike")
    except ValueError:
        # Strike column not found, skip highlighting
        return
    
    # Get number of columns and rows
    num_cols = len(cols)
    num_rows = len(df)
    
    # First, clear all highlights by setting bg to None/default for all option columns
    # This ensures old highlights are removed before applying new ones
    # We need to clear both call and put columns
    try:
        for row_idx in range(num_rows):
            for col_idx, col_name in enumerate(cols):
                # Only clear highlights on call/put columns (not Strike column)
                if "call" in col_name.lower() or "put" in col_name.lower():
                    try:
                        # Try to clear highlight by setting bg to None or empty
                        # If tksheet doesn't support this, new highlights will overwrite
                        sheet.highlight_cells(row=row_idx, column=col_idx, bg="")
                    except:
                        # If clearing doesn't work, we'll just overwrite with new highlights
                        pass
    except:
        # If clearing doesn't work, proceed - new highlights should overwrite old ones
        pass
    
    # Iterate through rows and highlight based on strike price
    for row_idx, (_, row) in enumerate(df.iterrows()):
        try:
            strike = float(row.get("Strike", 0) or 0)
            if strike <= 0:
                continue
            
            # Determine which columns to highlight based on strike vs stock price
            if strike <= stock_price:
                # Light red for strike <= stock price - only highlight "put" columns
                bg_color = "#ffcccc"
                # Highlight only columns with "put" in the name (case-insensitive)
                for col_idx, col_name in enumerate(cols):
                    if "put" in col_name.lower():
                        sheet.highlight_cells(row=row_idx, column=col_idx, bg=bg_color)
            else:
                # Light green for strike > stock price - only highlight "call" columns
                bg_color = "#ccffcc"
                # Highlight only columns with "call" in the name (case-insensitive)
                for col_idx, col_name in enumerate(cols):
                    if "call" in col_name.lower():
                        sheet.highlight_cells(row=row_idx, column=col_idx, bg=bg_color)
        except (ValueError, TypeError):
            # Skip rows with invalid strike prices
            continue

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
        "Bid_Call","Ask_Call","Delta_Call","Theta_Call","Gamma_Call","IV_Call","OI_Call","Prob_ITM_Call",
        "Strike",
        "Bid_Put","Ask_Put","Delta_Put","Theta_Put","Gamma_Put","IV_Put","OI_Put","Prob_ITM_Put"
    ]
    headers = [
        "Call Bid","Call Ask","Δ(Call)","Θ(Call)","Γ(Call)","IV(Call)","OI(Call)","% ITM (Call)",
        "Strike",
        "Put Bid","Put Ask","Δ(Put)","Θ(Put)","Γ(Put)","IV(Put)","OI(Put)","% ITM (Put)"
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
    # Set default column width to make columns thinner
    sheet.default_column_width(85)
    sheet.enable_bindings("all")
    # Disable editing to make table read-only
    sheet.disable_bindings("edit_cell", "edit_header", "edit_index")
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
        data.append(format_row_data(row, cols))
    
    # Update the sheet with new data
    sheet.set_sheet_data(data)
    
    # Highlight rows based on strike price vs stock price
    highlight_rows_by_strike(sheet, df, cols, state.price)

def on_expiration_change(self, event, symbol):
    ui = self.ticker_tabs.get(symbol)
    if not ui:
        return
    self.update_table_for_symbol(symbol, ui["exp_var"].get())