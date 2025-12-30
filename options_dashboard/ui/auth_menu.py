import tkinter as tk
from tkinter import messagebox
from data.schwab_auth import create_client
import os
from config import TOKEN_FILE

class AuthMenu(tk.Frame):
    def __init__(self, root, on_authenticated):
        super().__init__(root)
        self.on_authenticated = on_authenticated

        tk.Label(self, text="Schwab Option Dashboard", font=("Arial", 18, "bold")).pack(pady=20)

        self.status = tk.Label(self, text=self.token_status())
        self.status.pack(pady=5)

        tk.Button(self, text="Connect to Schwab", command=self.connect).pack(pady=5)
        tk.Button(self, text="Delete token.json", command=self.delete_token).pack(pady=5)

    def token_status(self):
        return "Token found." if os.path.exists(TOKEN_FILE) else "No token found."

    def delete_token(self):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        messagebox.showinfo("Token Deleted", "token.json removed.")
        self.status.config(text=self.token_status())

    def connect(self):
        try:
            client = create_client()
            self.on_authenticated(client)
        except Exception as e:
            messagebox.showerror("Authentication Failed", str(e))
