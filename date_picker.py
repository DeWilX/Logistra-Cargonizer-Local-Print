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
    def __init__(self, parent, variable):
        self.variable = variable
        try:
            self.selected = datetime.strptime(variable.get().strip(), '%d.%m.%Y').date()
        except ValueError:
            self.selected = date.today()
        self.year, self.month = self.selected.year, self.selected.month
        self.window = tk.Toplevel(parent)
        self.window.title(translate(parent, 'Izvēlies datumu'))
        self.window.transient(parent.winfo_toplevel())
        self.window.resizable(False, False)
        self.window.bind('<Escape>', lambda _: self.close())
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        body = ttk.Frame(self.window, padding=12)
        body.pack(fill='both', expand=True)
        header = ttk.Frame(body)
        header.pack(fill='x', pady=(0, 10))
        ttk.Button(header, text='‹', width=3, command=lambda: self.move(-1)).pack(side='left')
        self.title = tk.StringVar()
        ttk.Label(header, textvariable=self.title, anchor='center').pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(header, text='›', width=3, command=lambda: self.move(1)).pack(side='right')
        self.grid = ttk.Frame(body)
        self.grid.pack()
        footer = ttk.Frame(body)
        footer.pack(fill='x', pady=(10, 0))
        ttk.Button(footer, text='Šodien', command=lambda: self.choose(date.today())).pack(side='left')
        ttk.Button(footer, text='Notīrīt', command=lambda: self.choose(None)).pack(side='right')
        self.draw()
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x = min(parent.winfo_rootx(), self.window.winfo_screenwidth() - width)
        y = min(parent.winfo_rooty() + parent.winfo_height(), self.window.winfo_screenheight() - height)
        self.window.geometry(f'+{max(0, x)}+{max(0, y)}')
        self.window.grab_set()
        self.window.focus_set()

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
                button = ttk.Button(self.grid, text=str(day), width=4, command=lambda value=value: self.choose(value))
                button.grid(row=row, column=column, padx=1, pady=1)
                if value == self.selected:
                    button.state(['pressed'])

    def choose(self, value):
        self.variable.set(value.strftime('%d.%m.%Y') if value else '')
        self.close()

    def close(self):
        self.window.grab_release()
        self.window.destroy()
