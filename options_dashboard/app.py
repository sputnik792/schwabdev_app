from pathlib import Path

import customtkinter as ctk
from ui.auth_menu import AuthMenu
from ui.dashboard.dashboard import Dashboard
from style.custom_theme_controller import set_color_theme

from data.schwab_auth import (
    perform_pending_reset,
    schwab_tokens_exist,
    create_authenticated_client
)

ctk.set_appearance_mode("dark")  # "dark", "light", or "system"

THEME_NAME = "breeze"
theme_path = Path(__file__).resolve().parent / "import_themes" / f"{THEME_NAME}.json"
set_color_theme(THEME_NAME)  # ensure path works regardless of cwd

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
