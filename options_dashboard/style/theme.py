import customtkinter as ctk

# ------------------ Colors ------------------
BG_CONTENT = ("#f8fafc", "#020617")
BG_SIDEBAR = ("#e5e7eb", "#020617")
BG_APP     = ("#f1f5f9", "#0f172a")

CARD_BG    = ("#ffffff", "#020617")
TABLE_BG   = ("#ffffff", "#ffffff")

ACCENT_PRIMARY = "#3b82f6"
ACCENT_SUCCESS = "#10b981"
ACCENT_WARNING = "#f59e0b"

TEXT_PRIMARY = "#e5e7eb"
TEXT_SECONDARY = "#9ca3af"
TEXT_MUTED = "#64748b"

# ------------------ Fonts (lazy) ------------------
_fonts = None

def get_fonts():
    global _fonts
    if _fonts is None:
        _fonts = {
            "sm": ctk.CTkFont(size=12),
            "md": ctk.CTkFont(size=14),
            "lg": ctk.CTkFont(size=18, weight="bold"),
            "xl": ctk.CTkFont(size=24, weight="bold"),
            "xxl": ctk.CTkFont(size=28, weight="bold"),
        }
    return _fonts
