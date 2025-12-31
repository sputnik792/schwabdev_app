from tkinter import messagebox

def info(title, message):
    messagebox.showinfo(title, message)

def warning(title, message):
    messagebox.showwarning(title, message)

def error(title, message):
    messagebox.showerror(title, message)
