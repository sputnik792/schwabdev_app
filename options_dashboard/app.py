import tkinter as tk

from data.schwab_auth import (
    perform_pending_reset,
    schwab_tokens_exist,
    create_authenticated_client
)
from ui.auth_menu import AuthMenu
from ui.dashboard import Dashboard


perform_pending_reset()


def start_dashboard(client):
    auth.destroy()
    Dashboard(root, client)


root = tk.Tk()
root.title("Options Dashboard")

if schwab_tokens_exist():
    # Tokens exist → safe to create client
    client = create_authenticated_client()
    Dashboard(root, client)
else:
    # No tokens → show auth UI
    auth = AuthMenu(root, start_dashboard)

root.mainloop()
