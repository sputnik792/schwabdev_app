import tkinter as tk
from ui.auth_menu import AuthMenu
from ui.dashboard import Dashboard

def start_dashboard(client):
    auth.destroy()
    dashboard = Dashboard(root, client)
    dashboard.pack(fill="both", expand=True)

root = tk.Tk()
root.title("Schwab Option Chain Dashboard")
root.geometry("1400x800")

auth = AuthMenu(root, start_dashboard)
root.mainloop()
