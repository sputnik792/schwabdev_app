import tkinter as tk
from tkinter import ttk
import webbrowser

from ui import dialogs
from config import APP_KEY, CALLBACK_URL
from data.schwab_auth import (
    run_oauth_subprocess,
    create_authenticated_client
)


class AuthMenu(tk.Frame):
    def __init__(self, root, on_authenticated):
        super().__init__(root)
        self.on_authenticated = on_authenticated

        tk.Label(
            self,
            text="Schwab Authentication",
            font=("Arial", 16, "bold")
        ).pack(pady=12)

        self.status = tk.StringVar(value="Status: Not authenticated")
        tk.Label(self, textvariable=self.status).pack(pady=6)

        ttk.Button(
            self,
            text="Start Schwab Login",
            command=self.start_login
        ).pack(pady=6)

        tk.Label(
            self,
            text="Paste the FULL redirect URL here:"
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
        auth_url = (
            "https://api.schwabapi.com/v1/oauth/authorize"
            f"?client_id={APP_KEY}"
            f"&redirect_uri={CALLBACK_URL}"
            "&response_type=code"
        )

        webbrowser.open(auth_url)
        self.status.set("Status: Login started — complete in browser")

    def complete_login(self):
        redirect_url = self.url_box.get("1.0", "end").strip()
        if not redirect_url:
            dialogs.warning("Missing URL", "Paste the redirect URL.")
            return

        try:
            self.status.set("Status: Completing OAuth...")
            run_oauth_subprocess(redirect_url)

            client = create_authenticated_client()
            self.status.set("Status: Authenticated")
            self.on_authenticated(client)

        except Exception as e:
            dialogs.error("Authentication Failed", str(e))
