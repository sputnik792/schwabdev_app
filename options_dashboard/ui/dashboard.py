import tkinter as tk
from state.ticker_state import TickerState

class Dashboard(tk.Frame):
    def __init__(self, root, client):
        super().__init__(root)
        self.client = client

        tk.Label(self, text="Dashboard Loaded", font=("Arial", 16)).pack(pady=20)
        tk.Label(self, text="(Your existing UI logic goes here)").pack()
