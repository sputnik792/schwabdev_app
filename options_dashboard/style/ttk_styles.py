from tkinter import ttk

def apply_ttk_styles():
    style = ttk.Style()
    style.theme_use("default")

    style.configure(
        "TNotebook.Tab",
        padding=[14, 8],
        font=("Segoe UI", 13)
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
