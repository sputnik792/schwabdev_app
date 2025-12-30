import tkinter as tk
from ui.auth_menu import AuthMenu
from ui.dashboard import Dashboard

def start_dashboard(client):
    auth.destroy()
    dash = Dashboard(root, client)
    dash.pack(fill="both", expand=True)

root = tk.Tk()
root.title("Schwab Option Dashboard")
root.geometry("1200x800")

auth = AuthMenu(root, start_dashboard)
auth.pack(fill="both", expand=True)

root.mainloop()
