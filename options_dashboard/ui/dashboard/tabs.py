import tkinter as tk
from tkinter import ttk
from tksheet import Sheet
from style.theme import *
import customtkinter as ctk
import pandas as pd
from data.schwab_api import STRIKE_COUNT_OPTIONS
from state.strike_count_prefs import initial_strike_count_label

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

# Bright accents for max open-interest cells (stand out over ITM/OTM row colors)
_MAX_CALL_OI_BG = "#00e5ff"  # cyan
_MAX_PUT_OI_BG = "#ff9100"   # amber/orange
_MAX_OI_FG = "#000000"


def _oi_value(row, col_name: str) -> float:
    """Parse an OI cell to float; empty/invalid → 0."""
    try:
        val = row.get(col_name, 0)
        if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def highlight_max_oi_cells(sheet, df, cols):
    """
    Highlight the OI_Call / OI_Put cells with the highest open interest.
    Call max → bright cyan; Put max → bright amber. Ties highlight every match.
    """
    if not sheet or df is None or df.empty:
        return

    try:
        call_col_idx = cols.index("OI_Call")
    except ValueError:
        call_col_idx = None
    try:
        put_col_idx = cols.index("OI_Put")
    except ValueError:
        put_col_idx = None

    if call_col_idx is None and put_col_idx is None:
        return

    call_ois = [_oi_value(row, "OI_Call") for _, row in df.iterrows()]
    put_ois = [_oi_value(row, "OI_Put") for _, row in df.iterrows()]

    if call_col_idx is not None and call_ois:
        max_call = max(call_ois)
        if max_call > 0:
            for row_idx, oi in enumerate(call_ois):
                if oi == max_call:
                    try:
                        sheet.highlight_cells(
                            row=row_idx,
                            column=call_col_idx,
                            bg=_MAX_CALL_OI_BG,
                            fg=_MAX_OI_FG,
                        )
                    except TypeError:
                        sheet.highlight_cells(
                            row=row_idx, column=call_col_idx, bg=_MAX_CALL_OI_BG
                        )

    if put_col_idx is not None and put_ois:
        max_put = max(put_ois)
        if max_put > 0:
            for row_idx, oi in enumerate(put_ois):
                if oi == max_put:
                    try:
                        sheet.highlight_cells(
                            row=row_idx,
                            column=put_col_idx,
                            bg=_MAX_PUT_OI_BG,
                            fg=_MAX_OI_FG,
                        )
                    except TypeError:
                        sheet.highlight_cells(
                            row=row_idx, column=put_col_idx, bg=_MAX_PUT_OI_BG
                        )


def highlight_rows_by_strike(sheet, df, cols, stock_price):
    """
    Highlight rows in the sheet based on strike price vs stock price
    - Strike <= stock_price: light red (#ffcccc) on columns with "put" in name
    - Strike > stock_price: light green (#ccffcc) on columns with "call" in name
    Then highlight max OI_Call / OI_Put cells with bright accents.
    """
    if not sheet or df is None or df.empty:
        return

    # Find the Strike column index
    try:
        strike_col_idx = cols.index("Strike")
    except ValueError:
        strike_col_idx = None

    num_rows = len(df)

    # First, clear all highlights by setting bg to None/default for all option columns
    # This ensures old highlights are removed before applying new ones
    try:
        for row_idx in range(num_rows):
            for col_idx, col_name in enumerate(cols):
                if "call" in col_name.lower() or "put" in col_name.lower():
                    try:
                        sheet.highlight_cells(row=row_idx, column=col_idx, bg="")
                    except Exception:
                        pass
    except Exception:
        pass

    # ITM/OTM row coloring (requires a valid spot price)
    if strike_col_idx is not None and stock_price and stock_price > 0:
        for row_idx, (_, row) in enumerate(df.iterrows()):
            try:
                strike = float(row.get("Strike", 0) or 0)
                if strike <= 0:
                    continue

                if strike <= stock_price:
                    bg_color = "#ffcccc"
                    for col_idx, col_name in enumerate(cols):
                        if "put" in col_name.lower():
                            sheet.highlight_cells(row=row_idx, column=col_idx, bg=bg_color)
                else:
                    bg_color = "#ccffcc"
                    for col_idx, col_name in enumerate(cols):
                        if "call" in col_name.lower():
                            sheet.highlight_cells(row=row_idx, column=col_idx, bg=bg_color)
            except (ValueError, TypeError):
                continue

    # Overlay brightest accents on the peak call / put open-interest cells
    highlight_max_oi_cells(sheet, df, cols)

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
    
    # Restore data for symbols that already have data
    # This ensures data persists when tabs are rebuilt (e.g., when adding new tickers)
    def restore_data_after_rebuild():
        for symbol in self.preset_tickers:
            if symbol in self.ticker_tabs:
                ui = self.ticker_tabs[symbol]
                
                # Check if we have data for this symbol
                # Check backup first (multi-view data that was preserved when single-view overwrote it)
                state = None
                if hasattr(self, 'multi_view_data_backup') and symbol in self.multi_view_data_backup:
                    state = self.multi_view_data_backup[symbol]
                # Then check ticker_data
                elif symbol in self.ticker_data:
                    state = self.ticker_data[symbol]
                
                if state:
                    # Skip if this data was fetched in single view (has _from_single_view flag)
                    if hasattr(state, '_from_single_view') and state._from_single_view:
                        continue
                    
                    # Update price
                    if state.price > 0:
                        ui["price_var"].set(f"${state.price:.2f}")

                    if ui.get("strike_var"):
                        label = getattr(state, "strike_count_label", None) or initial_strike_count_label(symbol)
                        ui["strike_var"].set(label)
                    
                    # Update expiration dropdown and table if data exists
                    if state.exp_data_map:
                        expirations = list(state.exp_data_map.keys())
                        if expirations:
                            expirations.sort()
                            ui["exp_dropdown"].configure(values=expirations)
                            
                            # Try to restore previously selected expiration, or use first
                            current_exp = ui["exp_var"].get()
                            if current_exp and current_exp in expirations:
                                ui["exp_var"].set(current_exp)
                            else:
                                ui["exp_var"].set(expirations[0])
                            
                            # Update table with the selected expiration
                            self.update_table_for_symbol(symbol, ui["exp_var"].get())
    
    # Defer restoration to allow UI to update first
    if hasattr(self, 'root'):
        self.root.after(50, restore_data_after_rebuild)

def create_stock_tab(self, symbol):
    fonts = get_fonts()

    tab = ctk.CTkFrame(self.notebook)
    self.notebook.add(tab, text=symbol)

    price_var = tk.StringVar(value="—")
    exp_var = tk.StringVar()
    strike_var = tk.StringVar(value=initial_strike_count_label(symbol))

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
        width=200,
        font=ctk.CTkFont(size=14),
        dropdown_font=ctk.CTkFont(size=16),
        height=36
    )
    exp_dropdown.pack(side="left", padx=8)

    ctk.CTkLabel(row, text="Strikes:", font=fonts["md"], text_color=TEXT_MUTED).pack(side="left", padx=(16, 0))

    def on_strike_count_selected(selected_value):
        strike_var.set(selected_value)
        self.on_strike_count_change(symbol, selected_value)

    strike_dropdown = ctk.CTkOptionMenu(
        row,
        variable=strike_var,
        values=STRIKE_COUNT_OPTIONS,
        command=on_strike_count_selected,
        width=80,
        font=ctk.CTkFont(size=14),
        dropdown_font=ctk.CTkFont(size=16),
        height=36
    )
    strike_dropdown.pack(side="left", padx=8)

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
        "strike_var": strike_var,
        "strike_dropdown": strike_dropdown,
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
    
    # Extract actual symbol from key if it's a single view key (format: "_single_{symbol}")
    actual_symbol = symbol
    if symbol.startswith("_single_"):
        actual_symbol = symbol.replace("_single_", "")
    
    state = self.ticker_data.get(actual_symbol)
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