from pathlib import Path
import customtkinter as ctk

THEME_DIR = Path(__file__).resolve().parent.parent / "import_themes"

_current_theme = None
_theme_change_callback = None


def list_available_themes():
    if not THEME_DIR.exists():
        return []
    return sorted(p.stem for p in THEME_DIR.glob("*.json"))


def register_theme_change_callback(callback):
    global _theme_change_callback
    _theme_change_callback = callback


def set_color_theme(theme_name: str):
    global _current_theme

    theme_path = THEME_DIR / f"{theme_name}.json"
    if not theme_path.exists():
        return

    _current_theme = theme_name
    ctk.set_default_color_theme(str(theme_path))

    # 🔥 Instant rebuild
    if _theme_change_callback:
        _theme_change_callback()


def get_current_theme():
    return _current_theme
