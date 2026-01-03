from tkinter import ttk
from style.theme import ACCENT_PRIMARY, BG_CONTENT, TEXT_PRIMARY, TEXT_SECONDARY
from style.theme_controller import is_light_mode

def apply_ttk_styles():
    style = ttk.Style()
    style.theme_use("default")
    
    # Determine if we're in light or dark mode
    light_mode = is_light_mode()
    
    # Modern tab styling with sleek design
    # Active tab colors
    active_bg = ACCENT_PRIMARY
    active_fg = "#ffffff"
    
    # Inactive tab colors
    if light_mode:
        inactive_bg = "#e5e7eb"  # Light gray
        inactive_fg = "#64748b"  # Muted text
        border_color = "#cbd5e1"
    else:
        inactive_bg = "#1e293b"  # Dark slate
        inactive_fg = TEXT_SECONDARY
        border_color = "#334155"
    
    # Configure notebook style
    style.configure(
        "TNotebook",
        background=BG_CONTENT[1] if not light_mode else BG_CONTENT[0],
        borderwidth=0,
        tabmargins=[2, 0, 0, 0]  # Top, left, bottom, right margins
    )
    
    # Configure tab style - inactive tabs
    style.configure(
        "TNotebook.Tab",
        padding=[18, 10, 18, 10],  # More horizontal padding for modern look
        font=("Segoe UI", 13, "normal"),
        background=inactive_bg,
        foreground=inactive_fg,
        borderwidth=0,
        focuscolor="none"  # Remove focus outline
    )
    
    # Map active tab style with smooth transitions
    style.map(
        "TNotebook.Tab",
        background=[
            ("selected", active_bg),
            ("!selected", inactive_bg)
        ],
        foreground=[
            ("selected", active_fg),
            ("!selected", inactive_fg)
        ],
        expand=[("selected", [1, 1, 1, 0])]  # Expand padding when selected for modern look
    )

    style.configure(
        "Treeview",
        rowheight=30,
        font=("Segoe UI", 12)
    )

    style.configure(
        "Treeview.Heading",
        font=("Segoe UI", 13, "bold")
    )
