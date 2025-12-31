import os
import tkinter as tk
from tkinter import ttk
from ui import dialogs
from data.schwab_auth import create_client
from config import TOKEN_FILE


class AuthMenu(tk.Frame):
    def __init__(self, root, on_authenticated):
        super().__init__(root)
        self.on_authenticated = on_authenticated

        tk.Label(self, text="Schwab Option Dashboard", font=("Arial", 18, "bold")).pack(pady=16)

        self.status_var = tk.StringVar(value=self._token_status())
        tk.Label(self, textvariable=self.status_var).pack(pady=6)

        btns = tk.Frame(self)
        btns.pack(pady=8)

        ttk.Button(btns, text="Connect to Schwab", command=self.connect).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Delete token.json", command=self.delete_token).pack(side=tk.LEFT, padx=6)

        self.pack(fill="both", expand=True)

    def _token_status(self):
        return "Token found." if os.path.exists(TOKEN_FILE) else "No token found."

    def delete_token(self):
        try:
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
            self.status_var.set(self._token_status())
            dialogs.info("Token Deleted", "token.json has been removed.")
        except Exception as e:
            dialogs.error("Error", str(e))

    def connect(self):
        try:
            client = create_client()
            self.on_authenticated(client)
        except Exception as e:
            dialogs.error("Authentication Failed", str(e))
