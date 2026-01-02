import customtkinter as ctk

_current_theme = "Dark"

def set_theme(mode: str):
    global _current_theme
    if mode not in ("Dark", "Light"):
        return

    _current_theme = mode
    ctk.set_appearance_mode(mode)

def set_theme_from_switch(is_light: bool):
    set_theme("Light" if is_light else "Dark")

def is_light_mode():
    return _current_theme == "Light"

def current_icon():
    return "☀️" if is_light_mode() else "🌙"