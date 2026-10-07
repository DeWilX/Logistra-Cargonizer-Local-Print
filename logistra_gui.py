"""Unified Logistra Windows GUI; Tkinter and Python standard library."""
import contextlib
import base64
from datetime import datetime
import json
import os
import plistlib
from pathlib import Path
import queue
import sqlite3
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
import xml.etree.ElementTree as ET
from app_paths import initialize_config

import logistra as engine
from printer_setup import PrinterWindow

ROOT = engine.ROOT
_config_lock = threading.RLock()


def read_config():
    return json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))


def write_config(values):
    with _config_lock:
        cfg = read_config()
        cfg.update(values)
        temporary = ROOT / 'config.json.tmp'
        temporary.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(ROOT / 'config.json')
        return cfg


def save_key(key):
    if sys.platform == 'darwin':
        from mac_support import keychain_key
        keychain_key(key)
        os.environ.pop('CARGONIZER_API_KEY', None)
        return
    if os.name != 'nt':
        raise RuntimeError('API atslēgas šifrēšana pieejama Windows datorā.')
    from windows_support import save_windows_key
    save_windows_key(ROOT / 'api-key.dpapi', key)
    os.environ.pop('CARGONIZER_API_KEY', None)


def configure_startup(enabled):
    if sys.platform == 'darwin':
        directory = Path.home() / 'Library' / 'LaunchAgents'
        file = directory / 'app.logistra.print.plist'
        if enabled:
            directory.mkdir(parents=True, exist_ok=True)
            arguments = [sys.executable, '--startup'] if getattr(sys, 'frozen', False) else [sys.executable, str(ROOT / 'logistra_gui.py'), '--startup']
            payload = {'Label': 'app.logistra.print', 'ProgramArguments': arguments,
                       'WorkingDirectory': str(ROOT), 'RunAtLoad': True}
            file.write_bytes(plistlib.dumps(payload))
        else:
            file.unlink(missing_ok=True)
        return
    if os.name != 'nt':
        raise RuntimeError('Automātiska palaišana pieejama Windows datorā.')
    directory = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup'
    legacy = directory / 'Logistra.vbs'
    startup = directory / 'Logistra Print.lnk'
    if not enabled:
        legacy.unlink(missing_ok=True)
        startup.unlink(missing_ok=True)
        return
    executable = Path(sys.executable) if getattr(sys, 'frozen', False) else Path(sys.executable).with_name('pythonw.exe')
    if not executable.is_file():
        raise RuntimeError('pythonw.exe nav atrasts. Instalē pilnu Windows Python versiju.')
    from ui_theme import asset
    icon = ROOT / 'logistra.ico'
    shutil.copyfile(asset('logistra.ico'), icon)
    directory.mkdir(parents=True, exist_ok=True)
    arguments = '--startup' if getattr(sys, 'frozen', False) else f'"{Path(__file__).resolve()}" --startup'
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = '$ErrorActionPreference="Stop"; $shell=New-Object -ComObject WScript.Shell; '
    script += '$link=$shell.CreateShortcut(' + quote(startup) + '); '
    script += '$link.TargetPath=' + quote(executable) + '; $link.Arguments=' + quote(arguments) + '; '
    script += '$link.WorkingDirectory=' + quote(ROOT) + '; $link.IconLocation=' + quote(str(icon) + ',0') + '; '
    script += '$link.Description="Logistra Print"; $link.WindowStyle=7; $link.Save()'
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                    base64.b64encode(script.encode('utf-16le')).decode('ascii')],
                   check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    legacy.unlink(missing_ok=True)


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.stop = threading.Event()
        self.task_busy = False
        self.closing = False
        self.buttons = []
        cfg = read_config()
        root.title('Logistra — sūtījumi un etiķetes')
        root.geometry('940x790')
        root.minsize(800, 740)
        style = ttk.Style(root)
        style.configure('TButton', padding=(10, 8))
        shell = ttk.Frame(root, padding=18)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Logistra', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        self.status = tk.StringVar(value='Automātika apturēta')
        ttk.Label(shell, textvariable=self.status).pack(anchor='w', pady=(4, 10))
        tabs = ttk.Notebook(shell)
        tabs.pack(fill='both', expand=True)
        settings = ttk.Frame(tabs, padding=20)
        printing = ttk.Frame(tabs)
        shipments = ttk.Frame(tabs, padding=20)
        journal = ttk.Frame(tabs, padding=14)
        for frame, title in [(settings, 'API un automātika'), (printing, 'Printeris un pādruka'), (shipments, 'Sūtījumi'), (journal, 'Žurnāls')]:
            tabs.add(frame, text=title)
        self.printer_ui = PrinterWindow(printing, embedded=True)
        self.sender = tk.StringVar(value=str(cfg['sender_id']))
        self.key = tk.StringVar()
        self.path = tk.StringVar(value=cfg['list_path'])
        self.interval = tk.StringVar(value=str(cfg['poll_seconds']))
        self.verified = tk.BooleanVar(value=cfg['list_verified'])
        self.printing = tk.BooleanVar(value=cfg.get('auto_print', False))
        self.autostart = tk.BooleanVar(value=cfg.get('autostart', False))
        settings.columnconfigure(1, weight=1)
        for row, (label, variable, mask) in enumerate([
                ('Sender ID', self.sender, ''), ('API atslēga (tukšs = saglabāt esošo)', self.key, '•'),
                ('Sūtījumu saraksta API ceļš', self.path, ''), ('Pārbaudes intervāls sekundēs', self.interval, '')]):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky='w', padx=(0, 15), pady=8)
            ttk.Entry(settings, textvariable=variable, show=mask).grid(row=row, column=1, sticky='ew', pady=8)
        for row, (label, variable) in enumerate([
                ('Apstiprinu: jaunais sūtījums redzams sarakstā; saraksta pilnīgums pārbaudīts', self.verified),
                ('Automātiski drukāt (citādi tikai lejupielādēt PDF)', self.printing),
                ('Palaist automātiku pēc lietotāja pieteikšanās', self.autostart)], start=4):
            ttk.Checkbutton(settings, text=label, variable=variable).grid(row=row, column=0, columnspan=2, sticky='w', pady=8)
        ttk.Label(settings, text='Pirms automātikas: pārbaudi jaunu open sūtījumu un PDF testa druku.\nSaraksts ar vairākām lapām vēl netiek apstrādāts. Datoram jāpaliek ieslēgtam.', wraplength=780).grid(row=7, column=0, columnspan=2, sticky='w', pady=14)
        actions = ttk.Frame(settings)
        actions.grid(row=8, column=0, columnspan=2, sticky='w')
        for label, callback in [('Saglabāt', self.save), ('Pārbaudīt API', self.check_api), ('Pārbaudīt sarakstu', self.probe)]:
            self.button(actions, label, callback)
        controls = ttk.Frame(settings)
        controls.grid(row=9, column=0, columnspan=2, sticky='w', pady=15)
        self.button(controls, 'Saglabāt sākuma atskaiti', self.baseline)
        self.button(controls, 'Palaist automātiku', self.start)
        ttk.Button(controls, text='Apturēt', command=self.stop_worker).pack(side='left', padx=(0, 8))
        ttk.Button(settings, text='Minimizēt — turpināt fonā', command=root.iconify).grid(row=10, column=0, columnspan=2, sticky='w')
        self.identifier = tk.StringVar()
        entry = ttk.Frame(shipments)
        entry.pack(fill='x')
        ttk.Label(entry, text='Sūtījuma ID').pack(side='left', padx=(0, 10))
        ttk.Entry(entry, textvariable=self.identifier, width=22).pack(side='left', padx=(0, 10))
        self.button(entry, 'Lejupielādēt PDF', self.download)
        ttk.Button(entry, text='Atvērt PDF mapi', command=self.open_folder).pack(side='left')
        self.table = ttk.Treeview(shipments, columns=('id', 'status'), show='headings')
        self.table.heading('id', text='Sūtījuma ID')
        self.table.heading('status', text='Automātiskās apstrādes statuss')
        self.table.pack(fill='both', expand=True, pady=15)
        self.table.bind('<<TreeviewSelect>>', self.select_job)
        ttk.Button(shipments, text='Atsvaidzināt uzskaiti', command=self.refresh_jobs).pack(anchor='w')
        ttk.Label(shipments, text='Neskaidra druka netiek automātiski atkārtota. Pādrukai izmanto cilni “Printeris un pādruka”.', wraplength=780).pack(anchor='w', pady=12)
        self.logs = tk.Text(journal, wrap='word', state='disabled', font=('Consolas', 11))
        self.logs.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.receive)
        self.refresh_jobs()
        if '--startup' in sys.argv:
            root.after(500, root.iconify)
            if cfg.get('autostart'):
                root.after(1000, self.start)

    def button(self, frame, text, callback):
        button = ttk.Button(frame, text=text, command=callback)
        button.pack(side='left', padx=(0, 8))
        self.buttons.append(button)

    def log(self, message):
        line = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '  ' + str(message)
        self.status.set(str(message))
        self.logs.configure(state='normal')
        self.logs.insert('end', line + '\n')
        self.logs.see('end')
        self.logs.configure(state='disabled')
        (ROOT / 'data').mkdir(exist_ok=True)
        with (ROOT / 'data' / 'gui.log').open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')

    def snapshot(self):
        return {'sender_id': engine.shipment_id(self.sender.get()) if self.sender.get().strip() else '', 'list_path': self.path.get().strip(),
                'poll_seconds': max(5, int(self.interval.get())), 'list_verified': self.verified.get(),
                'auto_print': self.printing.get(), 'autostart': self.autostart.get()}

    def task(self, action, success):
        if self.task_busy:
            return
        self.task_busy = True
        for button in self.buttons:
            button.state(['disabled'])
        def run():
            try:
                self.events.put(('task', success, action(), None))
            except Exception as error:
                self.events.put(('task', success, None, str(error)))
        threading.Thread(target=run, daemon=True).start()

    def receive(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == 'log':
                self.log(event[1])
            elif event[0] == 'jobs':
                self.refresh_jobs()
            else:
                _, callback, result, error = event
                self.task_busy = False
                for button in self.buttons:
                    button.state(['!disabled'])
                if error:
                    self.log('Kļūda: ' + error)
                else:
                    callback(result)
        if self.closing and not self.task_busy and not self.printer_ui.busy and not (self.worker and self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(100, self.receive)

    def save(self):
        if self.worker and self.worker.is_alive():
            self.log('Vispirms apturi automātiku, lai mainītu API iestatījumus.')
            return
        try:
            values = self.snapshot()
            key = self.key.get()
        except Exception as error:
            self.log('Kļūda: ' + str(error))
            return
        def action():
            if key:
                save_key(key)
            configure_startup(values['autostart'])
            write_config(values)
        def completed(_):
            self.key.set('')
            self.log('Iestatījumi saglabāti. API atslēga netiek rādīta vai ierakstīta žurnālā.')
        self.task(action, completed)

    def check_api(self):
        def action():
            root = ET.fromstring(engine.Client(read_config()).get('/transport_agreements.xml'))
            if root.tag != 'transport-agreements':
                raise RuntimeError('Negaidīta API atbilde.')
        self.task(action, lambda _: self.log('API pieslēgums darbojas ar saglabātajiem iestatījumiem.'))

    def probe(self):
        path = self.path.get().strip()
        def action():
            client = engine.Client(read_config())
            ids = engine.parse_ids(client.get(path))
            return f'Sarakstā {len(ids)} sūtījumi; lapas: {client.pagination.get("Total-Pages")}. ID: {", ".join(ids[:10])}'
        self.task(action, self.log)

    def baseline(self):
        if self.worker and self.worker.is_alive():
            self.log('Vispirms apturi automātiku.')
            return
        def action():
            with engine.single_worker(), contextlib.closing(engine.database()) as db:
                ids = engine.Client(read_config()).ids()
                if db.execute("SELECT 1 FROM settings WHERE name='baseline'").fetchone():
                    raise RuntimeError('Sākuma atskaite jau saglabāta; tā netiks pārrakstīta.')
                with db:
                    db.executemany('INSERT OR IGNORE INTO jobs VALUES (?, ?)', [(i, 'baseline') for i in ids])
                    db.execute("INSERT INTO settings VALUES ('baseline', 'yes')")
                return len(ids)
        self.task(action, lambda count: (self.log(f'Sākuma atskaite: {count} esoši sūtījumi netiks drukāti.'), self.refresh_jobs()))

    def download(self, identifiers=None):
        try:
            identifiers = [engine.shipment_id(value) for value in identifiers] if identifiers is not None else [engine.shipment_id(self.identifier.get())]
        except Exception as error:
            self.log(str(error))
            return
        def action():
            client = engine.Client(read_config())
            files = []
            for identifier in identifiers:
                try:
                    files.append(engine.download_label(client, identifier, 'reprint-'))
                except Exception as error:
                    raise RuntimeError(f'Sūtījums {identifier}: {error}. Pirms kļūdas saglabāti {len(files)} PDF; pārējie nav apstrādāti.') from error
            return files
        self.task(action, lambda files: self.log(f'Saglabāti {len(files)} PDF izvēlētajā mapē. Manuāla lejupielāde nemaina automātisko uzskaiti.'))

    def start(self):
        if self.worker and self.worker.is_alive():
            self.log('Automātika jau darbojas.')
            return
        cfg = read_config()
        if cfg.get('auto_print') and engine.is_pdf_export_printer(cfg):
            self.log('Microsoft Print to PDF izmanto manuālai PDF saglabāšanai. Automātiskai drukai izvēlies fizisku printeri.')
            return
        if not cfg.get('list_verified'):
            self.log('Vispirms pārbaudi jaunu sūtījumu, apstiprini saraksta pārbaudi un saglabā iestatījumus.')
            return
        if cfg.get('auto_print') and (not cfg.get('printer') or not engine.pdf_executable(cfg).is_file()):
            self.log('Vispirms saglabā printeri un PDF drukāšanas programmas ceļu.')
            return
        self.stop.clear()
        self.worker = threading.Thread(target=self.watch, args=(cfg,), daemon=True)
        self.worker.start()

    def watch(self, cfg):
        report = lambda message: self.events.put(('log', message))
        try:
            with engine.single_worker(), contextlib.closing(engine.database()) as db:
                if not db.execute("SELECT 1 FROM settings WHERE name='baseline'").fetchone():
                    raise RuntimeError('Vispirms saglabā sākuma atskaiti.')
                client = engine.Client(cfg)
                report('Automātika darbojas: ' + ('drukā etiķetes' if cfg.get('auto_print') else 'tikai lejupielādē PDF'))
                while not self.stop.is_set():
                    try:
                        ids = set(client.ids())
                        ids.update(i for i, in db.execute("SELECT id FROM jobs WHERE status='downloaded'"))
                        for identifier in sorted(ids, key=int):
                            if self.stop.is_set():
                                break
                            before = db.execute('SELECT status FROM jobs WHERE id=?', (identifier,)).fetchone()
                            try:
                                engine.process(db, client, cfg, identifier, cfg.get('auto_print', False))
                                after = db.execute('SELECT status FROM jobs WHERE id=?', (identifier,)).fetchone()
                                if after != before:
                                    report(f'Sūtījums {identifier}: {after[0]}')
                            except Exception as error:
                                report(f'Sūtījums {identifier}: kļūda: {error}')
                        self.events.put(('jobs',))
                    except Exception as error:
                        report('Saraksta pārbaudes kļūda: ' + str(error))
                    self.stop.wait(max(5, int(cfg['poll_seconds'])))
        except Exception as error:
            report('Automātikas kļūda: ' + str(error))
        finally:
            report('Automātika apturēta')

    def stop_worker(self):
        self.stop.set()
        self.log('Apturēšana pieprasīta; pašreizējā lejupielāde vai druka tiks pabeigta.')

    def refresh_jobs(self):
        path = ROOT / 'data' / 'state.sqlite'
        if not path.exists():
            return
        try:
            with contextlib.closing(sqlite3.connect(path, timeout=1)) as db:
                rows = db.execute('SELECT id, status FROM jobs ORDER BY CAST(id AS INTEGER) DESC').fetchall()
        except sqlite3.Error:
            return
        self.table.delete(*self.table.get_children())
        labels = {'baseline': 'Esošs pirms palaišanas', 'downloaded': 'PDF lejupielādēts',
                  'submitted': 'Nosūtīts drukas rindai', 'submitting': 'Drukas rezultāts jāpārbauda', 'uncertain': 'Neskaidra druka — jāpārbauda'}
        for identifier, status in rows:
            from localization import translate
            self.table.insert('', 'end', values=(identifier, translate(self.root, labels.get(status, status))))

    def select_job(self, _):
        selected = self.table.selection()
        if selected:
            identifier = self.table.item(selected[0], 'values')[0]
            self.identifier.set(identifier)
            self.printer_ui.identifier.set(identifier)

    def open_folder(self):
        directory = engine.pdf_directory(read_config())
        directory.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            os.startfile(directory)
        elif sys.platform == 'darwin':
            subprocess.Popen(['/usr/bin/open', str(directory)])

    def close(self):
        if self.worker and self.worker.is_alive() or self.task_busy or self.printer_ui.busy:
            self.closing = True
            self.stop_worker()
            self.log('Aizver logu pēc pašreizējās darbības pabeigšanas. Minimizēšana ļauj turpināt fonā.')
        else:
            self.root.destroy()


if __name__ == '__main__':
    instance = None
    if sys.platform == 'win32' and '--self-test' not in sys.argv:
        from single_instance import WindowsInstance
        instance = WindowsInstance(ROOT)
        if not instance.primary:
            try:
                instance.notify()
            finally:
                instance.close()
            raise SystemExit(0)
    initialize_config()
    if '--self-test' in sys.argv and '--self-test-update' in sys.argv:
        import hashlib
        from updater import launch_replacement
        staged = Path(sys.argv[sys.argv.index('--self-test-update') + 1])
        report_path = sys.argv[sys.argv.index('--self-test-report') + 1]
        launch_replacement(staged, hashlib.sha256(staged.read_bytes()).hexdigest(),
                           restart_arguments=['--self-test', '--self-test-report', report_path])
        raise SystemExit(0)
    if '--self-test' in sys.argv:
        import platform
        from friendly_gui import FriendlyApp
        from shipment_browser import ShipmentBrowser
        from ui_theme import apply_theme, asset
        probe = tk.Tk()
        probe.withdraw()
        apply_theme(probe)
        icon = tk.PhotoImage(file=str(asset('logistra.png')))
        actions = tk.PhotoImage(file=str(asset('row-actions.png')))
        report = {'platform': sys.platform, 'arch': platform.machine(),
                  'frozen': bool(getattr(sys, 'frozen', False)), 'data_dir': str(ROOT),
                  'config_loaded': bool(read_config()), 'tk': probe.tk.call('info', 'patchlevel'),
                  'default_test_pdf_bundled': asset('default-test-label.pdf').read_bytes().startswith(b'%PDF-'),
                  'assets_loaded': icon.width() > 0 and actions.width() > 0}
        from version import VERSION, UPDATE_REPOSITORY
        report.update(version=VERSION, update_repository=UPDATE_REPOSITORY)
        if '--self-test-network' in sys.argv:
            from updater import github_opener
            from network_tls import verified_context
            import ssl
            context = verified_context()
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            with github_opener().open('https://github.com', timeout=30) as response:
                report['github_tls_checked'] = response.status == 200
            assert report['github_tls_checked']
        if sys.platform == 'win32':
            from tray_support import WindowsTray
            if '--self-test-tray' in sys.argv:
                import time
                errors = []
                tray = WindowsTray(probe, asset('logistra.ico'), lambda: None, errors.append)
                tray.hide()
                deadline = time.monotonic() + 5
                while not tray.ready and time.monotonic() < deadline:
                    probe.update()
                    time.sleep(0.01)
                report['tray_checked'] = tray.ready and tray.icon.visible and probe.state() == 'withdrawn' and not errors
                if report['tray_checked']:
                    tray.show()
                    probe.update()
                    report['tray_persistent'] = tray.icon.visible and probe.state() == 'normal'
                    tray.hide()
                    report['tray_checked'] = report['tray_persistent'] and probe.state() == 'withdrawn'
                if not report['tray_checked']:
                    probe.destroy()
                    raise RuntimeError('Windows tray self-test failed.')
            import tempfile
            from windows_support import read_windows_key, save_windows_key
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                key_path = Path(folder) / 'test-key.dpapi'
                save_windows_key(key_path, 'offline-self-test')
                report['dpapi_checked'] = read_windows_key(key_path) == 'offline-self-test'
                if not report['dpapi_checked']:
                    raise RuntimeError('Windows DPAPI self-test failed.')
        probe.destroy()
        if '--self-test-report' in sys.argv:
            Path(sys.argv[sys.argv.index('--self-test-report') + 1]).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if sys.stdout is not None:
            print(json.dumps(report))
        raise SystemExit(0)
    try:
        root = tk.Tk()
        from friendly_gui import FriendlyApp
        app = FriendlyApp(root)
        if sys.platform == 'win32' and getattr(sys, 'frozen', False) and read_config().get('autostart'):
            try:
                configure_startup(True)
            except Exception:
                app.log('Neizdevās atjaunināt Windows starta saīsni. Saglabā iestatījumus vēlreiz.')
        if instance is not None:
            instance.attach(root, app.restore_window)
        root.mainloop()
    finally:
        if instance is not None:
            instance.close()
