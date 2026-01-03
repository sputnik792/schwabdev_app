from pathlib import Path
import os

import customtkinter as ctk
from ui.auth_menu import AuthMenu
from ui.dashboard.dashboard import Dashboard
from style.custom_theme_controller import set_color_theme, list_available_themes
from state.app_state import get_state_value, save_app_state
from options_dashboard.config import STATE_FILE

from data.schwab_auth import (
    perform_pending_reset,
    schwab_tokens_exist,
    create_authenticated_client
)

ctk.set_appearance_mode("dark")  # "dark", "light", or "system"

# Load theme from state, default to first available theme if not set
# Themes list is now cached to avoid multiple file system scans
THEME_NAME = get_state_value("color_theme")
if not THEME_NAME:
    themes = list_available_themes()  # This will cache the result for subsequent calls
    THEME_NAME = themes[0] if themes else "breeze"

if THEME_NAME:
    set_color_theme(THEME_NAME)

perform_pending_reset()

def start_dashboard(client):
    # Create app_state.json if it doesn't exist (first-time user)
    if not os.path.exists(STATE_FILE):
        # Use cached themes if available, otherwise get them
        themes = list_available_themes()
        default_theme = themes[0] if themes else "breeze"
        initial_state = {
            "color_theme": default_theme,
            "exposure_model": "Gamma"
        }
        save_app_state(initial_state)
    
    auth.destroy()
    Dashboard(root, client)

# -----------------------------
# Root window
# -----------------------------
root = ctk.CTk()
root.title("Options Dashboard")
root.geometry("1400x700")
root.minsize(1200, 650)

if schwab_tokens_exist():
    # Create app_state.json if it doesn't exist (for users upgrading)
    if not os.path.exists(STATE_FILE):
        # Use cached themes if available
        themes = list_available_themes()
        default_theme = themes[0] if themes else "breeze"
        initial_state = {
            "color_theme": default_theme,
            "exposure_model": "Gamma"
        }
        save_app_state(initial_state)
    
    client = create_authenticated_client()
    Dashboard(root, client)
else:
    auth = AuthMenu(root, start_dashboard)

root.mainloop()
