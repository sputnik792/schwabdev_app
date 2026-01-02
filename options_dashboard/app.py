import customtkinter as ctk
from ui.auth_menu import AuthMenu
from ui.dashboard.dashboard import Dashboard

from data.schwab_auth import (
    perform_pending_reset,
    schwab_tokens_exist,
    create_authenticated_client
)

ctk.set_appearance_mode("dark")          # "dark", "light", or "system"
ctk.set_default_color_theme("dark-blue") # modern, clean accent

perform_pending_reset()

def start_dashboard(client):
    auth.destroy()
    Dashboard(root, client)

# -----------------------------
# Root window
# -----------------------------
root = ctk.CTk()
root.title("Options Dashboard")
root.geometry("1400x800")
root.minsize(1200, 700)

if schwab_tokens_exist():
    client = create_authenticated_client()
    Dashboard(root, client)
else:
    auth = AuthMenu(root, start_dashboard)


root.mainloop()
