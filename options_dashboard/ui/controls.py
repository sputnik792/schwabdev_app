import tkinter as tk

def add_spot_slider(parent, spot, callback):
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
    slider.pack(fill="x")
