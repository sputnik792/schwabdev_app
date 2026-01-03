from tkinter import messagebox
import tkinter as tk
from tkinter import ttk

def info(title, message):
    messagebox.showinfo(title, message)

def warning(title, message):
    messagebox.showwarning(title, message)

def error(title, message):
    messagebox.showerror(title, message)

def ask_yes_no(title, message):
    return messagebox.askyesno(title, message)

def show_timed_message(root, title, message, duration_ms=3000):
    """Show a timed message dialog that auto-closes after duration_ms"""
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.geometry("450x150")
    dialog.resizable(False, False)

    dialog.update_idletasks()

    # Center on screen
    screen_w = dialog.winfo_screenwidth()
    screen_h = dialog.winfo_screenheight()
    win_w = dialog.winfo_width()
    win_h = dialog.winfo_height()

    x = (screen_w // 2) - (win_w // 2)
    y = (screen_h // 2) - (win_h // 2)
    dialog.geometry(f"{win_w}x{win_h}+{x}+{y}")

    label = ttk.Label(
        dialog, 
        text=message, 
        wraplength=420,
        font=("Segoe UI", 12)
    )
    label.pack(expand=True, fill="both", padx=15, pady=15)
    dialog.update_idletasks()
    dialog.update()

    dialog.after(duration_ms, dialog.destroy)

    dialog.transient(root)
    dialog.grab_set()