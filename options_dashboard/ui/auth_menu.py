import tkinter as tk
from tkinter import ttk
import webbrowser

from ui import dialogs
from data.schwab_auth import (
    create_client,
    get_auth_url,
    complete_auth_from_redirect
)

class AuthMenu(tk.Frame):
    def __init__(self, root, on_authenticated):
        super().__init__(root)
        self.root = root
        self.on_authenticated = on_authenticated
        self.client = None

        tk.Label(
            self,
            text="Schwab Authentication",
            font=("Arial", 16, "bold")
        ).pack(pady=12)

        ttk.Button(
            self,
            text="Start Schwab Login",
            command=self.start_login
        ).pack(pady=6)

        tk.Label(
            self,
            text="After login, paste the FULL redirect URL here:"
        ).pack(pady=(12, 4))

        self.url_box = tk.Text(self, height=4, width=90)
        self.url_box.pack(padx=10)

        ttk.Button(
            self,
            text="Complete Login",
            command=self.complete_login
        ).pack(pady=10)

        self.pack(fill="both", expand=True)

    def start_login(self):
        try:
            self.client = create_client()
            url = get_auth_url(self.client)
            webbrowser.open(url)
        except Exception as e:
            dialogs.error("Error", str(e))

    def complete_login(self):
        try:
            redirect_url = self.url_box.get("1.0", "end").strip()
            if not redirect_url:
                dialogs.warning("Missing URL", "Please paste the redirect URL.")
                return

            client = complete_auth_from_redirect(self.client, redirect_url)
            self.on_authenticated(client)

        except Exception as e:
            dialogs.error("Authentication Failed", str(e))
