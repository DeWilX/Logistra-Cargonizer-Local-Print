"""Consistent light desktop appearance with clear controls and selection states."""
from pathlib import Path
import sys
import subprocess
import queue
import threading
import tkinter as tk
from tkinter import ttk


def asset(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / name


def window_geometry(screen_width, screen_height):
    width = min(1530, max(760, screen_width - 64))
    height = min(920, max(650, screen_height - 100))
    return width, height, max(0, (screen_width-width)//2), max(0, (screen_height-height)//2)


DARK_COLORS = {
    '#f5f7fb':'#171c26', '#243247':'#e5ebf5', '#ffffff':'#222b39',
    '#cdd5e2':'#46536a', '#edf0f5':'#293140', '#dce7fb':'#34476a',
    '#edf3ff':'#303d53', '#7a8799':'#99a7bc', '#edf1f7':'#252f40',
    '#52627a':'#b7c4d9', '#e2eaff':'#34476a', '#e8edf5':'#252f40',
    '#e1eaff':'#34476a', '#e9eef6':'#2c374b', '#475569':'#cbd6e8',
    '#dce9ff':'#304e7b', '#12376c':'#ffffff', '#e1e9f5':'#34476a',
    '#dae2ee':'#3b485e', '#f4f7fc':'#1c2432', '#b3c9ef':'#334e79',
}


def system_dark_mode():
    try:
        if sys.platform == 'win32':
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
                return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
        if sys.platform == 'darwin':
            result = subprocess.run(['/usr/bin/defaults', 'read', '-g', 'AppleInterfaceStyle'], capture_output=True, text=True, timeout=2)
            return result.returncode == 0 and result.stdout.strip().lower() == 'dark'
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def theme_color(widget, light):
    return DARK_COLORS.get(light, light) if getattr(widget.winfo_toplevel(), '_logistra_dark', False) else light


def watch_theme(root):
    if getattr(root, '_logistra_theme_mode', 'system') == 'system':
        if sys.platform == 'darwin':
            # Never wait for the defaults subprocess in Tk's event loop.
            results = queue.Queue()
            def detect():
                results.put(system_dark_mode())
            def receive():
                try:
                    dark = results.get_nowait()
                except queue.Empty:
                    root.after(50, receive)
                    return
                root._logistra_system_dark = dark
                if getattr(root, '_logistra_theme_mode', 'system') == 'system' and dark != root._logistra_dark:
                    apply_theme(root, dark)
                    root.event_generate('<<LogistraThemeChanged>>')
            threading.Thread(target=detect, daemon=True).start()
            root.after(50, receive)
            root.after(5000, lambda: watch_theme(root))
            return
        dark = system_dark_mode()
        if dark != root._logistra_dark:
            apply_theme(root, dark)
            root.event_generate('<<LogistraThemeChanged>>')
    root.after(5000, lambda: watch_theme(root))


def set_theme_mode(root, mode):
    if mode not in ('system', 'light', 'dark'):
        raise ValueError('Unknown appearance mode.')
    root._logistra_theme_mode = mode
    apply_theme(root)
    root.event_generate('<<LogistraThemeChanged>>')


def apply_theme(root, dark=None):
    if dark is None:
        mode = getattr(root, '_logistra_theme_mode', 'system')
        if mode == 'system':
            dark = getattr(root, '_logistra_system_dark', None) if sys.platform == 'darwin' else None
            if dark is None:
                dark = system_dark_mode()
                root._logistra_system_dark = dark
        else:
            dark = mode == 'dark'
    root._logistra_dark = dark
    def c(value):
        return DARK_COLORS.get(value, value) if root._logistra_dark else value
    style = ttk.Style(root)
    style.theme_use('clam')
    font = ('Helvetica', 12) if sys.platform == 'darwin' else ('Segoe UI', 11)
    root.configure(background=c('#f5f7fb'))
    root.option_add('*Font', font)
    style.configure('.', font=font, background=c('#f5f7fb'), foreground=c('#243247'))
    style.configure('TFrame', background=c('#f5f7fb'))
    style.configure('TLabel', background=c('#f5f7fb'))
    style.configure('TButton', padding=(16,11), background=c('#ffffff'), foreground=c('#243247'), bordercolor=c('#cdd5e2'), borderwidth=1, relief='flat', focusthickness=2, focuscolor=c('#84adff'))
    style.map('TButton', background=[('disabled',c('#edf0f5')), ('pressed',c('#dce7fb')), ('active',c('#edf3ff'))], foreground=[('disabled',c('#7a8799'))], bordercolor=[('focus',c('#155eef'))])
    style.configure('Primary.TButton', background=c('#155eef'), foreground='#ffffff', bordercolor=c('#155eef'), font=(font[0], font[1], 'bold'))
    style.map('Primary.TButton', background=[('disabled',c('#b3c9ef')), ('pressed',c('#1045b8')), ('active',c('#124fd0'))], foreground=[('disabled','#ffffff')])
    style.configure('Compact.TButton', padding=(10,5))
    style.configure('Compact.Primary.TButton', padding=(10,5))
    style.configure('Compact.TEntry', padding=4)
    style.configure('Compact.TCombobox', padding=4)
    style.configure('Compact.TRadiobutton', padding=(5,4))
    style.configure('Nav.TButton', padding=(16,7), background=c('#edf1f7'), foreground=c('#52627a'), borderwidth=0, relief='flat')
    style.map('Nav.TButton', background=[('pressed',c('#dce7fb')),('active',c('#e2eaff'))], foreground=[('disabled',c('#7a8799'))])
    style.configure('NavActive.TButton', padding=(16,7), background=c('#155eef'), foreground='#ffffff', borderwidth=0, relief='flat')
    style.map('NavActive.TButton', background=[('pressed',c('#1045b8')),('active',c('#124fd0'))], foreground=[('active','#ffffff')])
    style.configure('TNotebook', borderwidth=0, tabmargins=(0,8,0,0))
    style.configure('TNotebook.Tab', padding=(20,12), background=c('#e8edf5'), foreground=c('#52627a'))
    style.map('TNotebook.Tab', background=[('selected',c('#ffffff')), ('active',c('#e1eaff'))], foreground=[('selected',c('#155eef'))])
    style.configure('TEntry', fieldbackground=c('#ffffff'), padding=8, bordercolor=c('#cdd5e2'))
    style.configure('TCombobox', fieldbackground=c('#ffffff'), background=c('#ffffff'),
                    foreground=c('#243247'), arrowcolor=c('#243247'), padding=7,
                    bordercolor=c('#cdd5e2'), selectbackground=c('#dce9ff'), selectforeground=c('#12376c'))
    style.map('TCombobox', fieldbackground=[('readonly',c('#ffffff'))],
              foreground=[('disabled',c('#7a8799')), ('readonly',c('#243247'))],
              background=[('active',c('#edf3ff')), ('pressed',c('#dce7fb'))],
              arrowcolor=[('disabled',c('#7a8799')), ('active',c('#243247')), ('pressed',c('#243247'))])
    style.configure('Treeview', background=c('#ffffff'), fieldbackground=c('#ffffff'), foreground=c('#243247'), rowheight=40, borderwidth=0, indent=0)
    style.layout('Treeview.Item', [('Treeitem.padding', {'sticky':'nswe', 'children': [
        ('Treeitem.image', {'side':'left', 'sticky':'ns'}),
        ('Treeitem.text', {'side':'left', 'sticky':'nswe'})]})])
    style.configure('Treeview.Heading', background=c('#e9eef6'), foreground=c('#475569'), padding=(10,12), font=(font[0], font[1], 'bold'), relief='flat')
    style.map('Treeview', background=[('selected',c('#dce9ff'))], foreground=[('selected',c('#12376c'))])
    style.map('Treeview.Heading', background=[('active',c('#e1e9f5'))])
    style.configure('Heading.TLabel', font=(font[0],26,'bold'))
    style.configure('Title.TLabel', font=(font[0],15,'bold'))
    style.configure('Card.TLabelframe', padding=18, bordercolor=c('#dae2ee'))
    style.configure('TLabelframe.Label', font=(font[0],12,'bold'))
    style.configure('TCheckbutton', padding=5)
    style.configure('TRadiobutton', padding=(8,7))
    for control in ('TCheckbutton', 'TRadiobutton'):
        style.map(control,
                  background=[('active', c('#edf3ff')), ('disabled', c('#f5f7fb'))],
                  foreground=[('disabled', c('#7a8799')), ('active', c('#243247'))],
                  indicatorbackground=[('disabled', c('#edf0f5')), ('active', c('#ffffff'))],
                  indicatorforeground=[('disabled', c('#7a8799')), ('active', c('#243247'))])
    style.configure('TScrollbar', background=c('#e9eef6'), troughcolor=c('#f5f7fb'), arrowcolor=c('#243247'))
    root.option_add('*Text.background', c('#ffffff'))
    root.option_add('*Text.foreground', c('#243247'))
    root.option_add('*Text.insertBackground', c('#243247'))
    root.option_add('*TCombobox*Listbox.background', c('#ffffff'))
    root.option_add('*TCombobox*Listbox.foreground', c('#243247'))
    def update_text(parent):
        for widget in parent.winfo_children():
            if isinstance(widget, tk.Text):
                widget.configure(background=c('#ffffff'), foreground=c('#243247'), insertbackground=c('#243247'))
            update_text(widget)
    update_text(root)
    if not getattr(root, '_logistra_theme_watch', False):
        root._logistra_theme_watch = True
        root.after(5000, lambda: watch_theme(root))
    return style
