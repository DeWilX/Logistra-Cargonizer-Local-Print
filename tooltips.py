"""Small themed hover explanations without blocking Tk's event loop."""
import tkinter as tk
from tkinter import ttk
from ui_theme import theme_color


class Tooltip:
    def __init__(self, widgets, text):
        self.anchor = widgets[0]
        self.text = text
        self.timer = None
        self.window = None
        for widget in widgets:
            widget.bind('<Enter>', self.schedule, add='+')
            widget.bind('<Leave>', self.hide, add='+')
            widget.bind('<ButtonPress>', self.hide, add='+')
            widget.bind('<Destroy>', self.hide, add='+')

    def schedule(self, _=None):
        self.hide()
        self.timer = self.anchor.after(250, self.show)

    def show(self):
        self.timer = None
        if self.window is not None:
            return
        self.window = tk.Toplevel(self.anchor)
        self.window.withdraw()
        self.window.overrideredirect(True)
        border = tk.Frame(self.window, background=theme_color(self.anchor, '#cdd5e2'), padx=1, pady=1)
        border.pack(fill='both', expand=True)
        ttk.Label(border, textvariable=self.text, wraplength=360, padding=10).pack()
        self.window.update_idletasks()
        x = min(self.anchor.winfo_rootx(), max(0, self.window.winfo_screenwidth() - self.window.winfo_reqwidth() - 10))
        y = min(self.anchor.winfo_rooty() + self.anchor.winfo_height() + 8, max(0, self.window.winfo_screenheight() - self.window.winfo_reqheight() - 10))
        self.window.geometry(f'+{x}+{y}')
        self.window.deiconify()

    def hide(self, _=None):
        if self.timer is not None:
            try:
                self.anchor.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        if self.window is not None:
            window, self.window = self.window, None
            window.destroy()
