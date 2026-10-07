"""Windows tray callbacks are queued back to Tk's main thread."""
import queue


class WindowsTray:
    def __init__(self, root, icon_path, on_exit, on_error):
        import pystray
        from PIL import Image
        from localization import translate
        self.root = root
        self.on_exit = on_exit
        self.on_error = on_error
        self.events = queue.Queue()
        self.ready = False
        self.pending_hide = False
        self.closed = False
        with Image.open(icon_path) as image:
            picture = image.copy()
        self.icon = pystray.Icon('Logistra Print', picture, 'Logistra Print', menu=pystray.Menu(
            pystray.MenuItem(lambda item: translate(root, 'Atvērt Logistra Print'), lambda icon, item: self.events.put('show'), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: translate(root, 'Aizvērt'), lambda icon, item: self.events.put('exit'))))
        root.bind('<Destroy>', self.destroyed, add='+')
        self.icon.run_detached(setup=lambda icon: self.events.put('ready'))
        root.after(100, self.receive)
        root.after(5000, self.check_ready)

    def hide(self):
        self.pending_hide = True
        if self.ready:
            self.icon.visible = True
            self.root.withdraw()

    def show(self):
        self.pending_hide = False
        self.root.deiconify()
        self.root.state('normal')
        self.root.lift()
        self.root.focus_force()
        self.icon.visible = True

    def receive(self):
        if self.closed:
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event == 'ready':
                    self.ready = True
                    self.icon.visible = True
                    if self.pending_hide:
                        self.hide()
                elif event == 'show':
                    self.show()
                elif event == 'exit':
                    self.on_exit()
        except queue.Empty:
            pass
        except Exception:
            self.pending_hide = False
            self.root.deiconify()
            self.on_error('Neizdevās paslēpt logu system tray. Logs paliek atvērts.')
        if not self.closed:
            self.root.after(100, self.receive)

    def check_ready(self):
        if not self.closed and not self.ready:
            self.pending_hide = False
            self.on_error('System tray ikona nav gatava. Logs paliek atvērts.')

    def destroyed(self, event):
        if event.widget == self.root and not self.closed:
            self.closed = True
            self.icon.stop()
