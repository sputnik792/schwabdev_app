import customtkinter as ctk

_current_theme = "Dark"


def set_theme(mode: str):
    """
    mode: 'Dark' or 'Light'
    """
    global _current_theme
    if mode not in ("Dark", "Light"):
        return

    _current_theme = mode
    ctk.set_appearance_mode(mode)


def toggle_theme():
    global _current_theme
    new_mode = "Light" if _current_theme == "Dark" else "Dark"
    set_theme(new_mode)


def get_theme():
    return _current_theme