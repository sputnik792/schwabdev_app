import tkinter as tk
from tkinter import ttk

def chart_output_selector(parent, var):
    box = ttk.Combobox(
        parent,
        textvariable=var,
        values=["Browser", "Desktop"],
        state="readonly",
        width=10
    )
    box.pack(pady=5)
    return box


def exposure_model_selector(parent, var):
    btn = tk.Menubutton(parent, text="Exposure Model", relief=tk.RAISED)
    menu = tk.Menu(btn, tearoff=0)
    btn.config(menu=menu)

    for model in ["Gamma", "Vanna", "Volga", "Charm"]:
        menu.add_radiobutton(label=model, variable=var, value=model)

    btn.pack(pady=5, padx=10, fill=tk.X)
    return btn


def spot_slider(parent, spot, callback):
    slider = tk.Scale(
        parent,
        from_=spot * 0.9,
        to=spot * 1.1,
        resolution=0.5,
        orient=tk.HORIZONTAL,
        label="Spot Scenario",
        command=lambda v: callback(float(v))
    )
    slider.set(spot)
    slider.pack(fill="x", padx=10, pady=5)
    return slider
