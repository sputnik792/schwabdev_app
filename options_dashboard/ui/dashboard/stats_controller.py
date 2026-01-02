import customtkinter as ctk
import numpy as np
import datetime

from style.theme import *
from style.theme import get_fonts


def open_stats_breakdown(self):
    fonts = get_fonts()

    tab_id = self.notebook.select()
    symbol = self.notebook.tab(tab_id, "text")

    state = self.ticker_data.get(symbol)
    ui = self.ticker_tabs.get(symbol)
    exp = ui["exp_var"].get()

    df = state.exp_data_map.get(exp)
    if df is None or df.empty:
        return

    df = df.replace("", 0)

    total_call_oi = df["OI_Call"].sum()
    total_put_oi = df["OI_Put"].sum()

    pcr = total_put_oi / total_call_oi if total_call_oi else 0

    win = ctk.CTkToplevel(self.root)
    win.geometry("520x360")
    win.title("Stats Breakdown")

    ctk.CTkLabel(
        win,
        text=f"{symbol} Stats — {exp}",
        font=fonts["lg"]
    ).pack(pady=12)

    card = ctk.CTkFrame(win, corner_radius=14)
    card.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(card, text="Put / Call Ratio", font=fonts["md"]).pack(pady=(20, 4))
    ctk.CTkLabel(card, text=f"{pcr:.3f}", font=fonts["xl"], text_color=ACCENT_PRIMARY).pack()
