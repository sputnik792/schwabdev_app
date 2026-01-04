import tkinter as tk
from tksheet import Sheet
import random
import string

def rand_word():
    return ''.join(random.choices(string.ascii_uppercase, k=5))

root = tk.Tk()
root.title("tksheet example")

headers = [rand_word() for _ in range(5)]
data = [[random.randint(1, 100) for _ in range(5)] for _ in range(10)]

sheet = Sheet(
    root,
    data=data,
    headers=headers,
    width=600,
    height=300
)
sheet.pack(fill="both", expand=True)

sheet.enable_bindings("all")

# Highlight a single cell
sheet.highlight_cells(row=2, column=3, bg="yellow")

root.mainloop()



import ttkbootstrap as tb
from ttkbootstrap.widgets.tableview import Tableview
import random
import string

def rand_word():
    return ''.join(random.choices(string.ascii_uppercase, k=5))

app = tb.Window(themename="flatly")
app.title("ttkbootstrap Tableview example")

headers = [rand_word() for _ in range(5)]
rows = [
    [random.randint(1, 100) for _ in range(5)]
    for _ in range(10)
]

table = Tableview(
    master=app,
    coldata=headers,
    rowdata=rows,
    paginated=False,
    searchable=False,
    bootstyle="primary"
)
table.pack(fill="both", expand=True, padx=10, pady=10)

# Highlight a row (cell-level coloring is not supported)
table.view.selection_set(table.view.get_children()[2])

app.mainloop()

