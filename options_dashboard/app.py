import tkinter as tk

from ui.auth_menu import AuthMenu
from ui.dashboard import Dashboard
from data.schwab_auth import try_create_client_with_tokens


def start_dashboard(client):
    auth.destroy()
    Dashboard(root, client)


root = tk.Tk()
root.title("Options Dashboard")

# 🔑 AUTO-AUTH CHECK
client = try_create_client_with_tokens()

if client:
    # Tokens exist and are valid → skip auth UI
    Dashboard(root, client)
else:
    # No valid tokens → show auth UI
    auth = AuthMenu(root, start_dashboard)

root.mainloop()
