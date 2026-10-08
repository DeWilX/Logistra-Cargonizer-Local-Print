"""Small native Tk calendar, no additional runtime dependencies."""
import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk
from localization import translate

MONTHS = ('Janvāris', 'Februāris', 'Marts', 'Aprīlis', 'Maijs', 'Jūnijs',
          'Jūlijs', 'Augusts', 'Septembris', 'Oktobris', 'Novembris', 'Decembris')


def shift_month(year, month, offset):
    value = year * 12 + month - 1 + offset
    return value // 12, value % 12 + 1


class DatePicker:
    def __init__(self, parent, variable, minimum=None, maximum=None):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        previous = getattr(self.root, '_date_picker', None)
        if previous is not None:
            previous.close()
        self.root._date_picker = self
        self.minimum, self.maximum = minimum, maximum
        self.closed = False
        self.variable = variable
        try:
            self.selected = datetime.strptime(variable.get().strip(), '%d.%m.%Y').date()
        except ValueError:
            self.selected = date.today()
        self.year, self.month = self.selected.year, self.selected.month
        # A child frame is an in-app popover, never another OS window.
        self.window = ttk.Frame(self.root, borderwidth=1, relief='solid')
        body = ttk.Frame(self.window, padding=8)
        body.pack(fill='both', expand=True)
        header = ttk.Frame(body)
        header.pack(fill='x', pady=(0, 10))
        previous_month = ttk.Button(header, text='‹', width=3, style='Compact.TButton', command=lambda: self.move(-1))
        previous_month.pack(side='left')
        self.title = tk.StringVar()
        ttk.Label(header, textvariable=self.title, anchor='center').pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(header, text='›', width=3, style='Compact.TButton', command=lambda: self.move(1)).pack(side='right')
        self.grid = ttk.Frame(body)
        self.grid.pack()
        footer = ttk.Frame(body)
        footer.pack(fill='x', pady=(10, 0))
        today = ttk.Button(footer, text='Šodien', style='Compact.TButton', command=lambda: self.choose(date.today()))
        today.pack(side='left')
        if not self.allowed(date.today()):
            today.state(['disabled'])
        ttk.Button(footer, text='Notīrīt', style='Compact.TButton', command=lambda: self.choose(None)).pack(side='right')
        self.draw()
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x = parent.winfo_rootx() - self.root.winfo_rootx()
        y = parent.winfo_rooty() - self.root.winfo_rooty() + parent.winfo_height()
        if y + height > self.root.winfo_height():
            y -= height + parent.winfo_height()
        self.window.place(x=max(0, min(x, self.root.winfo_width() - width)), y=max(0, y))
        self.window.lift()
        self.bindings = [(event, self.root.bind(event, callback, add='+')) for event, callback in
                         [('<ButtonPress-1>', self.outside), ('<Escape>', self.escape),
                          ('<Configure>', self.resized)]]
        previous_month.focus_set()

    def allowed(self, value):
        return value is None or ((self.minimum is None or value >= self.minimum) and
                                 (self.maximum is None or value <= self.maximum))

    def outside(self, event):
        if not str(event.widget).startswith(str(self.window) + '.') and event.widget != self.window:
            self.close(restore_focus=False)

    def escape(self, _):
        self.close()
        return 'break'

    def resized(self, event):
        if event.widget == self.root:
            self.close(restore_focus=False)

    def move(self, offset):
        year, month = shift_month(self.year, self.month, offset)
        if 1 <= year <= 9999:
            self.year, self.month = year, month
            self.draw()

    def draw(self):
        for child in self.grid.winfo_children():
            child.destroy()
        self.title.set(f'{MONTHS[self.month-1]} {self.year}')
        for column, name in enumerate(('Pr', 'Ot', 'Tr', 'Ce', 'Pk', 'Se', 'Sv')):
            ttk.Label(self.grid, text=name, anchor='center', width=4).grid(row=0, column=column, pady=(0, 4))
        for row, week in enumerate(calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month), start=1):
            for column, day in enumerate(week):
                if not day:
                    ttk.Label(self.grid, text='', width=4).grid(row=row, column=column)
                    continue
                value = date(self.year, self.month, day)
                button = ttk.Button(self.grid, text=str(day), width=3, style='Compact.TButton', command=lambda value=value: self.choose(value))
                button.grid(row=row, column=column, padx=1, pady=1)
                if value == self.selected:
                    button.state(['pressed'])
                if not self.allowed(value):
                    button.state(['disabled'])

    def choose(self, value):
        if not self.allowed(value):
            return
        self.variable.set(value.strftime('%d.%m.%Y') if value else '')
        self.close()

    def close(self, restore_focus=True):
        if self.closed:
            return
        self.closed = True
        for event, binding in getattr(self, 'bindings', []):
            self.root.unbind(event, binding)
        self.root._date_picker = None
        self.window.destroy()
        if restore_focus and self.parent.winfo_exists():
            self.parent.focus_set()
