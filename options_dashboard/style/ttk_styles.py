from tkinter import ttk

def apply_ttk_styles():
    style = ttk.Style()
    style.theme_use("default")

    style.configure(
        "TNotebook.Tab",
        padding=[26, 14],
        font=("Segoe UI", 14)
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
