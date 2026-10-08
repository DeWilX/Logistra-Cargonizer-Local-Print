"""Equal-height section buttons instead of platform-dependent notebook tabs."""
import tkinter as tk
from tkinter import ttk

from ui_theme import theme_color


class ScrollableSection(ttk.Frame):
    """Keep all setup controls reachable on smaller Windows screens."""
    def __init__(self, parent, padding=0):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')
        self.body = ttk.Frame(self.canvas, padding=padding)
        self.body._navigation_section = self
        self.content_id = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.content_size = None
        self.body.bind('<Configure>', self.resize)
        self.canvas.bind('<Configure>', self.resize)
        root = self.winfo_toplevel()
        root.bind('<MouseWheel>', self.wheel, add='+')
        root.bind('<<LogistraThemeChanged>>', lambda _: self.update_theme(), add='+')
        self.update_theme()

    def resize(self, _=None):
        size = (self.canvas.winfo_width(), max(self.canvas.winfo_height(), self.body.winfo_reqheight()))
        if size == self.content_size:
            return
        self.content_size = size
        self.canvas.itemconfigure(self.content_id, width=size[0], height=size[1])
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def wheel(self, event):
        if not self.winfo_ismapped():
            return
        widget = event.widget
        while widget is not None and widget != self:
            widget = getattr(widget, 'master', None)
        if widget == self and self.body.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta / 120) if abs(event.delta) >= 120 else -event.delta, 'units')
            return 'break'

    def update_theme(self):
        self.canvas.configure(background=theme_color(self, '#f5f7fb'))


class SectionNavigation(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.bar = ttk.Frame(self)
        self.bar.pack(fill='x', pady=(0,6))
        self.content = ttk.Frame(self)
        self.content.pack(fill='both', expand=True)
        self.items = []
        self.active = None

    def add(self, frame, text):
        button = ttk.Button(self.bar, text=text, style='Nav.TButton', command=lambda: self.select(frame))
        self.items.append((frame, button))
        frame.place(in_=self.content, x=0, y=0, relwidth=1, relheight=1)
        self.reorder()
        if self.active is None:
            self.select(frame)
        else:
            self.active.tkraise()

    def insert(self, index, frame):
        item = next(item for item in self.items if item[0] == frame)
        self.items.remove(item)
        self.items.insert(index, item)
        self.reorder()

    def reorder(self):
        for _, button in self.items:
            button.pack_forget()
        for _, button in self.items:
            button.pack(side='left', padx=(0,8), ipady=1)

    def select(self, frame=None):
        if frame is None:
            return self.active
        if isinstance(frame, int):
            frame = self.items[frame][0]
        frame = getattr(frame, '_navigation_section', frame)
        if frame == self.active:
            return
        for section, button in self.items:
            button.configure(style='NavActive.TButton' if section == frame else 'Nav.TButton')
        frame.tkraise()
        self.active = frame
