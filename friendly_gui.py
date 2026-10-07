"""Guided desktop interface, sharing the existing print and polling engine."""
import contextlib
import json
from pathlib import Path
import queue
import sqlite3
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

import logistra as engine
from logistra_gui import App, ROOT, read_config, write_config, save_key, configure_startup
from printer_setup import PrinterWindow, reprint_label, save_printer, label_file, save_pdf_copy, choose_pdf_destination, prepare_pdf_directory, saved_labels
from ui_theme import apply_theme, asset, window_geometry, set_theme_mode
from navigation import SectionNavigation, ScrollableSection
from localization import LANGUAGES, Locale, install_widgets, translate
from version import VERSION, UPDATE_REPOSITORY


def verify_open_shipment(cfg, identifier):
    identifier = engine.shipment_id(identifier)
    client = engine.Client({**cfg, 'list_verified': True})
    if identifier not in client.ids():
        raise ValueError('Šis sūtījums nav jauno sūtījumu sarakstā. Izveido jaunu open sūtījumu un mēģini vēlreiz.')
    root = ET.fromstring(client.get(f'/consignments/{identifier}.xml'))
    item = root.find('consignment')
    if item is None or item.findtext('id') != identifier or item.findtext('state') != 'open':
        raise ValueError('Pārbaudei vajadzīgs jauns sūtījums ar open statusu.')
    client.pdf(identifier)
    return identifier


def prepare_baseline(cfg):
    with engine.single_worker(), contextlib.closing(engine.database()) as db:
        if db.execute("SELECT 1 FROM settings WHERE name='baseline'").fetchone():
            return 0
        ids = engine.Client(cfg).ids()
        with db:
            db.executemany('INSERT OR IGNORE INTO jobs VALUES (?, ?)', [(i, 'baseline') for i in ids])
            db.execute("INSERT INTO settings VALUES ('baseline', 'yes')")
        return len(ids)


def print_setup_matches(cfg):
    identity = [cfg.get('printer'), cfg.get('print_backend'), str(engine.pdf_executable(cfg))]
    return bool(not engine.is_pdf_export_printer(cfg) and cfg.get('printer_tested') and cfg.get('tested_print_setup') == identity)


class FriendlyApp(App):
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.stop = threading.Event()
        self.task_busy = False
        self.closing = False
        self.buttons = []
        self.tray = None
        cfg = read_config()
        root._logistra_locale = Locale(cfg.get('language', 'lv'))
        install_widgets()
        self.sender = tk.StringVar(value=str(cfg['sender_id']))
        self.key = tk.StringVar()
        self.path = tk.StringVar(value=cfg['list_path'])
        self.interval = tk.StringVar(value=str(cfg['poll_seconds']))
        self.verified = tk.BooleanVar(value=cfg['list_verified'])
        self.printing = tk.BooleanVar(value=cfg.get('auto_print', True))
        self.autostart = tk.BooleanVar(value=cfg.get('autostart', False))
        self.close_to_tray = tk.BooleanVar(value=cfg.get('close_to_tray', True))
        self.theme_labels = {'system': 'Sistēmas tēma', 'light': 'Gaišs', 'dark': 'Tumšs'}
        theme_mode = cfg.get('theme', 'system')
        if theme_mode not in self.theme_labels:
            theme_mode = 'system'
        self.theme = tk.StringVar(value=self.theme_labels[theme_mode])
        root._logistra_theme_mode = theme_mode
        self.identifier = tk.StringVar()
        self.status = tk.StringVar(value='Sāksim ar pieslēguma pārbaudi')
        self.activity = tk.StringVar(value='Izpildi trīs soļus zemāk. Iestatījumi saglabājas šajā datorā.')
        self.summary = tk.StringVar()
        self.progress = tk.StringVar()
        root.title('Logistra Print')
        width, height, x, y = window_geometry(root.winfo_screenwidth(), root.winfo_screenheight())
        root.geometry(f'{width}x{height}+{x}+{y}')
        root.minsize(min(width,1100), min(height,760))
        style = apply_theme(root)
        self.app_icon = tk.PhotoImage(file=str(asset('logistra.png')))
        root.iconphoto(True, self.app_icon)
        shell = ttk.Frame(root, padding=22)
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x')
        self.header_icon = self.app_icon.subsample(16, 16)
        ttk.Label(header, image=self.header_icon).pack(side='left', padx=(0, 14))
        title_font = ('Helvetica' if sys.platform == 'darwin' else 'Segoe UI', 28, 'bold')
        ttk.Label(header, text='Logistra Print', style='Heading.TLabel', font=title_font).pack(side='left')
        ttk.Label(shell, textvariable=self.status, style='Title.TLabel').pack(anchor='w', pady=(16, 4))
        ttk.Label(shell, textvariable=self.summary).pack(anchor='w', pady=(0, 12))
        status_row = ttk.Frame(shell)
        status_row.pack(anchor='w', pady=(0, 10))
        self.status_dots = []
        for label in ('Konts', 'Printeris', 'Sūtījumi'):
            dot = ttk.Label(status_row, text='●', foreground='#ef4444', font=('Segoe UI', 12))
            dot.pack(side='left', padx=(0, 5))
            ttk.Label(status_row, text=label).pack(side='left', padx=(0, 20))
            self.status_dots.append(dot)
        self.tabs = SectionNavigation(shell)
        self.tabs.pack(fill='both', expand=True)
        home_section = ScrollableSection(self.tabs, padding=18)
        printer_section = ScrollableSection(self.tabs)
        settings_section = ScrollableSection(self.tabs, padding=20)
        self.home = home_section.body
        printer = printer_section.body
        settings = settings_section.body
        journal = ttk.Frame(self.tabs, padding=12)
        for frame, name in [(home_section, 'Sākums'), (printer_section, 'Printeris un PDF'), (settings_section, 'Iestatījumi'), (journal, 'Darbību žurnāls')]:
            self.tabs.add(frame, text=name)
        shipments = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(shipments, text='Cargonizer sūtījumi')
        self.tabs.insert(1, shipments)
        self.settings_tab = settings
        self.printer_tab = printer
        self.printer_ui = PrinterWindow(printer, embedded=True, on_print=self.confirm_print)
        from shipment_browser import ShipmentBrowser
        self.shipments_browser = ShipmentBrowser(shipments, self)
        setup = ttk.LabelFrame(self.home, text='Pirmā iestatīšana', style='Card.TLabelframe')
        self.setup_card = setup
        setup.pack(fill='x', pady=(0, 12))
        ttk.Label(setup, textvariable=self.progress, wraplength=820).pack(anchor='w', pady=(0, 10))
        actions = ttk.Frame(setup)
        actions.pack(anchor='w')
        self.setup_buttons = [
            self.button(actions, '1. Pieslēgt kontu', lambda: self.tabs.select(settings)),
            self.button(actions, '2. Izvēlēties printeri', lambda: self.tabs.select(printer)),
            self.button(actions, '3. Pārbaudīt jaunu sūtījumu', self.verify_shipment)]
        self.manual_setup_button = self.button(actions, 'Apstiprināt manuāli', self.manual_confirm)
        self.setup_state = None
        row = ttk.Frame(self.home)
        row.pack(fill='x', pady=(0, 12))
        self.button(row, 'Palaist automātiku', self.start)
        ttk.Button(row, text='Apturēt', command=self.stop_worker).pack(side='left', padx=(0, 10))
        self.interval_status = tk.StringVar(value=f'Pārbaude ik pēc {max(5, int(cfg["poll_seconds"]))} sekundēm')
        ttk.Label(row, textvariable=self.interval_status).pack(side='left')
        ttk.Checkbutton(self.home, text='Automātiski drukāt jaunās etiķetes (izslēgts = tikai saglabāt PDF)', variable=self.printing).pack(anchor='w', pady=(0, 12))
        manual = ttk.LabelFrame(self.home, text='Etiķete vai pādruka', style='Card.TLabelframe')
        manual.pack(fill='x', pady=(0, 12))
        ttk.Label(manual, text='Sūtījuma ID vai ref. / order numurs (piemēram, ORD-123456789)').pack(anchor='w')
        inputs = ttk.Frame(manual)
        inputs.pack(fill='x', pady=(8, 0))
        lookup_entry = ttk.Entry(inputs, textvariable=self.identifier, width=28)
        lookup_entry.pack(side='left', padx=(0, 10))
        lookup_entry.bind('<Return>', lambda _: self.lookup_reference())
        self.button(inputs, 'Meklēt', self.lookup_reference)
        self.button(inputs, 'Lejupielādēt PDF', self.download)
        self.button(inputs, 'Pādrukāt etiķeti', self.quick_reprint)
        ttk.Button(inputs, text='Atvērt PDF mapi', command=self.open_folder).pack(side='left')
        ttk.Label(self.home, text='Pēdējie sūtījumi', style='Title.TLabel').pack(anchor='w', pady=(4, 8))
        self.table = ttk.Treeview(self.home, columns=('id', 'status'), show='headings', height=6)
        self.table.heading('id', text='Sūtījums')
        self.table.heading('status', text='Statuss')
        self.table.column('id', width=180, stretch=False)
        self.table.pack(fill='both', expand=True)
        self.table.bind('<<TreeviewSelect>>', self.select_job)
        ttk.Label(self.home, text='Izvēlies sūtījumu un nospied “Pādrukāt etiķeti”. Pādruka ir viena papildu kopija.', wraplength=820).pack(anchor='w', pady=(8, 0))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text='Savienojums ar Cargonizer', style='Title.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 16))
        for row_index, (name, variable, mask) in enumerate([('Sender ID', self.sender, ''), ('API atslēga', self.key, '•')], start=1):
            ttk.Label(settings, text=name).grid(row=row_index, column=0, sticky='w', padx=(0, 15), pady=8)
            ttk.Entry(settings, textvariable=variable, show=mask).grid(row=row_index, column=1, sticky='ew', pady=8)
        ttk.Label(settings, text='API atslēgu atrodi Cargonizer iestatījumos. Tukšs lauks saglabā esošo atslēgu.', wraplength=760).grid(row=3, column=0, columnspan=2, sticky='w', pady=(4, 14))
        connection = ttk.Frame(settings)
        connection.grid(row=4, column=0, columnspan=2, sticky='w')
        self.button(connection, 'Saglabāt un pārbaudīt', self.connect)
        self.button(connection, 'Aizvērt pirmo iestatīšanu', self.manual_confirm)
        preferences = ttk.Frame(settings)
        preferences.grid(row=5, column=0, columnspan=2, sticky='ew', pady=18)
        ttk.Checkbutton(preferences, text='Palaist pēc Windows pieteikšanās (system tray)' if sys.platform == 'win32' else 'Palaist pēc datora lietotāja pieteikšanās', variable=self.autostart).pack(anchor='w')
        if sys.platform == 'win32':
            ttk.Checkbutton(preferences, text='Aizverot logu, turpināt system tray',
                            variable=self.close_to_tray, command=self.save_close_preference).pack(anchor='w', pady=(6, 0))
            ttk.Label(preferences, text='Izvēle saglabājas uzreiz. Lai izietu, tray ikonas izvēlnē izvēlies “Aizvērt”.').pack(anchor='w', pady=(4, 0))
        appearance = ttk.Frame(preferences)
        appearance.pack(anchor='w', pady=(12, 0))
        ttk.Label(appearance, text='Tēma:').pack(side='left', padx=(0, 12))
        theme_picker = ttk.Combobox(appearance, textvariable=self.theme,
                                    values=list(self.theme_labels.values()), state='readonly', width=18)
        theme_picker.pack(side='left')
        theme_picker.bind('<<ComboboxSelected>>', self.save_theme)
        language_row = ttk.Frame(preferences)
        language_row.pack(anchor='w', pady=(12, 0))
        ttk.Label(language_row, text='Valoda:').pack(side='left', padx=(0, 12))
        self.language = tk.StringVar(value=LANGUAGES[root._logistra_locale.language])
        language_picker = ttk.Combobox(language_row, textvariable=self.language,
                                      values=list(LANGUAGES.values()), state='readonly', width=18)
        language_picker.pack(side='left')
        language_picker.bind('<<ComboboxSelected>>', self.save_language)
        updates = ttk.LabelFrame(preferences, text='Atjauninājumi', padding=12)
        updates.pack(fill='x', pady=(16, 0))
        ttk.Label(updates, text='Versija: ' + VERSION).pack(anchor='w')
        ttk.Label(updates, text='GitHub repozitorijs (owner/repo):').pack(anchor='w', pady=(8, 4))
        self.update_repository = tk.StringVar(value=cfg.get('update_repository') or UPDATE_REPOSITORY)
        ttk.Entry(updates, textvariable=self.update_repository).pack(fill='x')
        self.check_updates_on_start = tk.BooleanVar(value=cfg.get('check_updates_on_start', True))
        ttk.Checkbutton(updates, text='Pārbaudīt atjauninājumus palaižot', variable=self.check_updates_on_start,
                        command=self.save_update_preferences).pack(anchor='w', pady=(8, 0))
        update_actions = ttk.Frame(updates)
        update_actions.pack(anchor='w', pady=(8, 0))
        self.button(update_actions, 'Pārbaudīt atjauninājumus', self.check_updates)
        self.button(update_actions, 'Lejupielādēt un atjaunināt', self.install_update)
        self.update_status = tk.StringVar(value='Atjauninājumi no publiska GitHub repozitorija. Iestatījumi saglabājas.')
        ttk.Label(updates, textvariable=self.update_status, wraplength=730).pack(anchor='w', pady=(8, 0))
        self.pending_update = None
        ttk.Label(preferences, text='PDF saglabāšanas mape:').pack(anchor='w', pady=(16, 4))
        pdf_location = ttk.Frame(preferences)
        pdf_location.pack(fill='x')
        self.pdf_folder = tk.StringVar(value=str(engine.pdf_directory(cfg)))
        ttk.Entry(pdf_location, textvariable=self.pdf_folder, state='readonly').pack(side='left', fill='x', expand=True, padx=(0, 12))
        self.button(pdf_location, 'Izvēlēties mapi', self.choose_pdf_folder)
        ttk.Label(preferences, text='Izvēle saglabājas uzreiz. Esošie PDF tiek nokopēti jaunajā mapē.', wraplength=760).pack(anchor='w', pady=(4, 0))
        self.advanced = ttk.Frame(settings)
        advanced_button = ttk.Button(settings, text='Papildu iestatījumi', command=self.toggle_advanced)
        advanced_button.grid(row=6, column=0, columnspan=2, sticky='w')
        self.advanced_visible = False
        for row_index, (label, variable) in enumerate([('API saraksta ceļš', self.path), ('Intervāls sekundēs', self.interval)]):
            ttk.Label(self.advanced, text=label).grid(row=row_index, column=0, sticky='w', padx=(0, 12), pady=8)
            ttk.Entry(self.advanced, textvariable=variable, width=45).grid(row=row_index, column=1, sticky='ew', pady=8)
        ttk.Label(self.advanced, text='Minimālais pārbaudes intervāls: 5 sekundes.').grid(row=3, column=0, columnspan=2, sticky='w')
        ttk.Checkbutton(self.advanced, text='Tikai saglabāt PDF (bez automātiskas drukas)', variable=self.printing, onvalue=False, offvalue=True).grid(row=2, column=0, columnspan=2, sticky='w', pady=8)
        self.button(self.advanced_row(settings), 'Saglabāt iestatījumus', self.save)
        ttk.Label(settings, text='Datoram jāpaliek ieslēgtam. Ja ieslēgta turpināšana system tray, loga aizvēršana neaptur automātiku.' if sys.platform == 'win32' else 'Datoram jāpaliek ieslēgtam. Minimizēts logs turpina darbu; aizvērts logs aptur automātiku.', wraplength=760).grid(row=9, column=0, columnspan=2, sticky='w', pady=18)
        self.logs = tk.Text(journal, wrap='word', state='disabled', font=('Courier', 11))
        self.logs.pack(fill='both', expand=True)
        ttk.Label(shell, textvariable=self.activity, wraplength=930).pack(anchor='w', pady=(12, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.receive)
        root.after(500, self.update_dashboard)
        self.refresh_jobs()
        root.after(1200, self.load_on_open)
        root.after(4500, self.check_updates_on_open)
        if sys.platform == 'win32':
            self.initialize_tray()
        if '--startup' in sys.argv or '--start-hidden' in sys.argv:
            self.startup_hide_timer = root.after(500, self.hide_to_tray)
            if '--startup' in sys.argv and cfg.get('autostart'):
                root.after(1000, self.start)
        if '--resume-automation' in sys.argv:
            root.after(1000, self.start)

    def advanced_row(self, frame):
        row = ttk.Frame(frame)
        row.grid(row=8, column=0, columnspan=2, sticky='w', pady=14)
        return row

    def save_language(self, _=None):
        language = next(key for key, label in LANGUAGES.items() if label == self.language.get())
        try:
            write_config({'language': language})
        except Exception as error:
            self.log('Kļūda: ' + str(error))
            return
        self.root._logistra_locale.set_language(language)
        self.shipments_browser.render()
        self.refresh_jobs()

    def snapshot(self):
        from updater import repository_name
        values = super().snapshot()
        repository = self.update_repository.get().strip()
        values.update(update_repository=repository_name(repository) if repository else '',
                      check_updates_on_start=self.check_updates_on_start.get())
        return values

    def save_update_preferences(self):
        from updater import repository_name
        value = self.update_repository.get().strip()
        try:
            repository = repository_name(value) if value else ''
            write_config({'update_repository': repository, 'check_updates_on_start': self.check_updates_on_start.get()})
            self.update_repository.set(repository)
            return repository
        except Exception as error:
            self.update_status.set('Kļūda: ' + str(error))
            return None

    def check_updates_on_open(self):
        if self.closing or '--self-test' in sys.argv:
            return
        if not self.check_updates_on_start.get() or not self.update_repository.get().strip():
            return
        if self.task_busy:
            self.root.after(1000, self.check_updates_on_open)
            return
        self.check_updates(automatic=True)

    def check_updates(self, automatic=False, install=False):
        from updater import check_release
        repository = self.save_update_preferences()
        if not repository:
            if repository == '' and not automatic:
                self.update_status.set('Norādi GitHub repozitoriju.')
            return
        self.update_status.set('Pārbauda GitHub Releases…')
        def action():
            try:
                return check_release(repository), None
            except Exception as error:
                return None, str(error)
        def completed(result):
            release, error = result
            self.pending_update = release
            if error:
                self.update_status.set('Atjauninājumu pārbaude neizdevās: ' + error)
            elif release:
                self.update_status.set('Pieejama jauna versija: ' + release['version'])
                self.log('Pieejama jauna versija: ' + release['version'])
                if install:
                    self.install_update()
            else:
                self.update_status.set('Jau lieto jaunāko versiju.')
        self.task(action, completed)

    def install_update(self):
        if not self.pending_update:
            self.check_updates(install=True)
            return
        if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
            self.update_status.set('Automātiska EXE aizstāšana pieejama Windows EXE versijā.')
            return
        from updater import download_release, launch_replacement, repository_name
        try:
            if repository_name(self.update_repository.get()) != self.pending_update['repository']:
                self.pending_update = None
                self.check_updates(install=True)
                return
        except ValueError as error:
            self.update_status.set('Kļūda: ' + str(error))
            return
        release = self.pending_update
        self.update_status.set('Lejupielādē un pārbauda atjauninājumu…')
        def completed(staged):
            try:
                launch_replacement(staged, release['sha256'], self.root.state() == 'withdrawn',
                                   bool(self.worker and self.worker.is_alive()))
            except Exception as error:
                self.update_status.set('Kļūda: ' + str(error))
                return
            self.log('Atjauninājums pārbaudīts. Sagaida pašreizējās darbības un pārstartē lietotni.')
            self.exit_application()
        self.task(lambda: download_release(release, ROOT / 'updates'), completed)

    def load_on_open(self):
        if self.closing or '--self-test' in sys.argv:
            return
        if self.task_busy:
            self.root.after(500, self.load_on_open)
            return
        try:
            engine.api_key()
        except Exception:
            return
        self.shipments_browser.load()

    def toggle_advanced(self):
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced.grid(row=7, column=0, columnspan=2, sticky='ew', pady=12)
        else:
            self.advanced.grid_remove()

    def choose_pdf_folder(self):
        if self.task_busy or self.printer_ui.busy or self.worker and self.worker.is_alive():
            self.log('Vispirms apturi automātiku un sagaidi pašreizējās darbības pabeigšanu.')
            return
        cfg = read_config()
        destination = filedialog.askdirectory(parent=self.root, title='Izvēlies PDF saglabāšanas mapi',
                                              initialdir=str(engine.pdf_directory(cfg)), mustexist=True)
        if not destination:
            return
        def action():
            directory = prepare_pdf_directory(cfg, destination)
            write_config({'pdf_directory': directory})
            return directory
        def completed(directory):
            self.pdf_folder.set(directory)
            self.printer_ui.history['values'] = saved_labels()
            self.log(f'PDF mape saglabāta: {directory}. Esošie PDF nokopēti; drukas vēsture saglabāta.')
        self.task(action, completed)

    def log(self, message):
        super().log(translate(self.root, message))
        self.activity.set(str(message))

    def update_dashboard(self):
        cfg = read_config()
        self.interval_status.set(f'Pārbaude ik pēc {max(5, int(cfg["poll_seconds"]))} sekundēm')
        running = bool(self.worker and self.worker.is_alive())
        printer_found = cfg.get('printer') in self.printer_ui.names
        printer_ready = printer_found and print_setup_matches(cfg)
        ready = bool(cfg.get('api_verified') and cfg.get('list_verified') and printer_ready)
        self.status.set('Automātiskā druka darbojas' if running and cfg.get('auto_print') else 'PDF lejupielāde darbojas' if running else 'Gatavs drukāšanai' if ready else 'Iestatījumi jāpārbauda' if cfg.get('setup_dismissed') else 'Pabeidz pirmo iestatīšanu')
        self.summary.set(f'Printeris: {cfg.get("printer") if printer_found else "nav iestatīts"}   •   Sender ID: {cfg.get("sender_id") or "nav iestatīts"}')
        steps = [('Konts pieslēgts', cfg.get('api_verified')), ('Printeris apstiprināts', printer_ready), ('Sūtījumu ielāde apstiprināta', cfg.get('list_verified'))]
        self.progress.set('   •   '.join(('✓ ' if done else 'Nav pārbaudīts: ') + name for name, done in steps))
        for dot, (_, done) in zip(self.status_dots, steps):
            dot.configure(foreground='#16a34a' if done else '#ef4444')
        state = (tuple(bool(done) for _, done in steps), bool(cfg.get('setup_dismissed')))
        if state != self.setup_state:
            self.setup_state = state
            for button in self.setup_buttons + [self.manual_setup_button]:
                button.pack_forget()
            checks, dismissed = state
            for button, done in zip(self.setup_buttons, checks):
                if not done:
                    button.pack(side='left', padx=(0,10))
            if not all(checks):
                self.manual_setup_button.pack(side='left', padx=(0,10))
            if all(checks) or dismissed:
                self.setup_card.pack_forget()
            elif not self.setup_card.winfo_manager():
                self.setup_card.pack(fill='x', pady=(0,12), before=self.home.winfo_children()[1])
        self.root.after(1000, self.update_dashboard)

    def refresh_jobs(self):
        selected = self.table.selection()
        identifier = self.table.item(selected[0], 'values')[0] if selected else None
        super().refresh_jobs()
        if identifier:
            for row in self.table.get_children():
                if self.table.item(row, 'values')[0] == identifier:
                    self.table.selection_set(row)
                    break

    def connect(self):
        if self.worker and self.worker.is_alive():
            self.log('Vispirms apturi automātiku.')
            return
        try:
            values = self.snapshot()
            key = self.key.get()
        except Exception as error:
            self.log('Pārbaudi ievadītos iestatījumus: ' + str(error))
            return
        def action():
            old = read_config()
            changed = key or old.get('sender_id') != values['sender_id'] or old.get('list_path') != values['list_path']
            if key:
                save_key(key)
            if changed:
                values.update(api_verified=False, list_verified=False)
            cfg = write_config(values)
            configure_startup(values['autostart'])
            root = ET.fromstring(engine.Client(cfg).get('/transport_agreements.xml'))
            if root.tag != 'transport-agreements':
                raise ValueError('Cargonizer pieslēgums nav apstiprināts.')
            write_config({'api_verified': True})
        def complete(_):
            self.key.set('')
            self.verified.set(read_config()['list_verified'])
            self.log('Konts pieslēgts. Tagad izvēlies printeri un izdrukā testa etiķeti.')
            self.tabs.select(self.home)
            self.root.after(150, self.shipments_browser.load)
        self.task(action, complete)

    def save(self):
        if self.worker and self.worker.is_alive():
            self.log('Apturi automātiku pirms iestatījumu maiņas.')
            return
        try:
            values = self.snapshot()
            self.interval.set(str(values['poll_seconds']))
        except Exception as error:
            self.log('Pārbaudi iestatījumus: ' + str(error))
            return
        if self.key.get() or read_config()['sender_id'] != values['sender_id']:
            self.connect()
            return
        def action():
            old = read_config()
            if old['list_path'] != values['list_path']:
                values['list_verified'] = False
            configure_startup(values['autostart'])
            write_config(values)
        self.task(action, lambda _: self.log('Iestatījumi saglabāti.'))

    def confirm_print(self, cfg):
        if messagebox.askyesno('Pārbaudi testa etiķeti', 'Vai etiķete fiziski izdrukājās pareizajā izmērā un svītrkodi nav nogriezti?', parent=self.root):
            save_printer(cfg['printer'], str(engine.pdf_executable(cfg)), cfg.get('print_backend', 'sumatra'))
            current = read_config()
            write_config({'printer_tested': True, 'printer_confirmation': 'test-print', 'tested_print_setup': [current.get('printer'), current.get('print_backend'), str(engine.pdf_executable(current))]})
            self.log('Printeris pārbaudīts un saglabāts.')
        else:
            write_config({'printer_tested': False})
            self.log('Pārbaudi papīra izmēru, printera rindu un atkārto testa druku.')

    def manual_confirm(self):
        try:
            write_config({'setup_dismissed': True})
        except Exception as error:
            self.log('Neizdevās saglabāt izvēli: ' + str(error))
            return
        self.setup_card.pack_forget()
        self.log('Pirmās iestatīšanas bloks paslēpts.')

    def verify_shipment(self):
        if not read_config().get('api_verified'):
            self.tabs.select(self.settings_tab)
            self.log('Vispirms pieslēdz kontu ar “Saglabāt un pārbaudīt”.')
            return
        from tkinter import simpledialog
        identifier = simpledialog.askstring('Jaunā sūtījuma pārbaude', 'Izveido jaunu open sūtījumu Cargonizer.\nIevadi tā ID no lapas adreses:', parent=self.root)
        if not identifier:
            return
        def action():
            result = verify_open_shipment(read_config(), identifier)
            write_config({'list_verified': True})
            return result
        def complete(identifier):
            self.verified.set(True)
            self.identifier.set(identifier)
            self.log(f'Jaunais sūtījums {identifier} atrasts, PDF pieejams. Vari ieslēgt automātisko druku.')
        self.task(action, complete)

    def lookup_reference(self, completed=None):
        value = self.identifier.get().strip()
        if not value:
            self.log('Ievadi sūtījuma ID vai ref. / order numuru.')
            return
        if value.isdecimal():
            identifier = engine.shipment_id(value)
            self.identifier.set(identifier)
            if completed:
                completed()
            else:
                self.log(f'Sūtījums {identifier} izvēlēts. Vari lejupielādēt PDF vai pādrukāt etiķeti.')
            return
        from reference_search import find_reference
        self.log(f'Meklē order numuru {value} visā sūtījumu vēsturē…')
        def found(rows):
            if not rows:
                self.log(f'Sūtījums ar ref. / order numuru {value} nav atrasts.')
                return
            def choose(identifier):
                self.identifier.set(identifier)
                self.printer_ui.identifier.set(identifier)
                self.log(f'Order {value}: izvēlēts sūtījums {identifier}.')
                if completed:
                    completed()
            if len(rows) == 1:
                choose(rows[0]['id'])
                return
            dialog = tk.Toplevel(self.root)
            dialog.title('Izvēlies order sūtījumu')
            dialog.transient(self.root)
            dialog.geometry('760x360')
            table = ttk.Treeview(dialog, columns=('id', 'recipient', 'created'), show='headings', selectmode='browse')
            for name, label in [('id', 'Sūtījuma ID'), ('recipient', 'Saņēmējs'), ('created', 'Datums')]:
                table.heading(name, text=label)
            table.pack(fill='both', expand=True, padx=12, pady=12)
            for row in rows:
                table.insert('', 'end', iid=row['id'], values=(row['id'], row['recipient'], row['created'][:10]))
            def accept():
                if table.selection():
                    identifier = table.selection()[0]
                    dialog.destroy()
                    choose(identifier)
            ttk.Button(dialog, text='Izvēlēties', command=accept).pack(pady=(0, 12))
            table.bind('<Double-1>', lambda _: accept())
            dialog.grab_set()
        self.task(lambda: find_reference(read_config(), value, lambda message: self.events.put(('log', message))), found)

    def download(self, identifiers=None):
        if identifiers is None and not self.identifier.get().strip().isdecimal():
            self.lookup_reference(lambda: self.download())
            return
        super().download(identifiers)

    def quick_reprint(self, identifiers=None):
        if identifiers is None and not self.identifier.get().strip().isdecimal():
            self.lookup_reference(lambda: self.quick_reprint())
            return
        if identifiers is not None:
            try:
                identifiers = [engine.shipment_id(value) for value in identifiers]
            except ValueError as error:
                self.log(str(error))
                return
            if len(identifiers) > 1:
                self.reprint_multiple(identifiers)
                return
            if identifiers:
                self.identifier.set(identifiers[0])
        cfg = read_config()
        if engine.is_pdf_export_printer(cfg):
            try:
                identifier = engine.shipment_id(self.identifier.get())
            except ValueError:
                self.log('Ievadi sūtījuma ID vai izvēlies sūtījumu tabulā.')
                return
            def prepared(file):
                destination = choose_pdf_destination(self.root, file.name.removeprefix('reprint-').removeprefix('test-'))
                if destination:
                    self.task(lambda: save_pdf_copy(file, destination),
                              lambda _: self.log('Oriģinālā PDF kopija saglabāta izvēlētajā mapē. Druka nav veikta.'))
            self.task(lambda: label_file(cfg, identifier), prepared)
            return
        if not messagebox.askyesno('Pādrukāt etiķeti?', 'Tas izdrukās vienu papildu kopiju. Vai iepriekšējais darbs vairs negaida printera rindā?', parent=self.root):
            return
        try:
            identifier = engine.shipment_id(self.identifier.get())
        except ValueError:
            self.log('Ievadi sūtījuma ID vai izvēlies sūtījumu tabulā.')
            return
        self.task(lambda: reprint_label(cfg, identifier), lambda _: self.log(f'Etiķete {identifier} nosūtīta printerim vēlreiz.'))

    def reprint_multiple(self, identifiers):
        cfg = read_config()
        if engine.is_pdf_export_printer(cfg):
            def prepared(files):
                destination = filedialog.askdirectory(parent=self.root, title=f'Saglabāt {len(files)} etiķešu PDF',
                                                      initialdir=str(engine.pdf_directory(cfg)), mustexist=True)
                if not destination:
                    return
                targets = [Path(destination) / file.name.removeprefix('reprint-').removeprefix('test-') for file in files]
                existing = [target for source, target in zip(files, targets) if target.exists() and source.resolve() != target.resolve()]
                if existing and not messagebox.askyesno('Aizstāt PDF failus?', f'Izvēlētajā mapē jau ir {len(existing)} PDF ar tādu pašu nosaukumu. Aizstāt tos?', parent=self.root):
                    return
                def export():
                    for source, target in zip(files, targets):
                        save_pdf_copy(source, target)
                    return len(files)
                self.task(export, lambda count: self.log(f'Saglabāti {count} oriģinālie PDF izvēlētajā mapē. Druka nav veikta.'))
            self.task(lambda: [label_file(cfg, identifier) for identifier in identifiers], prepared)
            return
        if not messagebox.askyesno('Pādrukāt atlasītās etiķetes?', f'Printerim nosūtīs {len(identifiers)} etiķetes, vienu kopiju no katras. Vai iepriekšējie darbi vairs negaida printera rindā?', parent=self.root):
            return
        def action():
            for index, identifier in enumerate(identifiers):
                try:
                    reprint_label(cfg, identifier)
                except Exception as error:
                    raise RuntimeError(f'Sūtījums {identifier}: {error}. Pirms kļūdas printerim nosūtītas {index} etiķetes; pārējās nav apstrādātas.') from error
                self.events.put(('log', f'Etiķete {identifier} nosūtīta printerim. Pārbaudi fizisko izdruku.'))
        self.task(action, lambda _: self.log(f'Printerim nosūtītas {len(identifiers)} atlasītās etiķetes.'))

    def start(self):
        if self.task_busy or self.worker and self.worker.is_alive():
            return
        cfg = read_config()
        cfg['auto_print'] = self.printing.get()
        if cfg['auto_print'] and engine.is_pdf_export_printer(cfg):
            self.log('Microsoft Print to PDF izmanto manuālai PDF saglabāšanai. Automātiskai drukai izvēlies fizisku printeri vai izslēdz automātisko druku.')
            self.tabs.select(self.printer_tab)
            return
        if not cfg.get('api_verified') or not cfg.get('list_verified'):
            self.log('Pabeidz konta pieslēgšanu un jaunā sūtījuma pārbaudi.')
            self.tabs.select(self.home)
            return
        if cfg.get('auto_print') and not print_setup_matches(cfg):
            self.log('Veic testa druku un apstiprini printera rezultātu.')
            self.tabs.select(self.printer_tab)
            return
        def action():
            write_config({'auto_print': cfg['auto_print']})
            return prepare_baseline(cfg)
        def complete(count):
            self.log(f'Sagatavots. {count} pašlaik esoši sūtījumi automātiski netiks drukāti.')
            super(FriendlyApp, self).start()
        self.task(action, complete)

    def save_theme(self, _=None):
        mode = next(mode for mode, label in self.theme_labels.items() if label == self.theme.get())
        try:
            write_config({'theme': mode})
        except Exception:
            mode = read_config().get('theme', 'system')
            self.theme.set(self.theme_labels.get(mode, self.theme_labels['system']))
            self.log('Neizdevās saglabāt tēmas izvēli.')
            return
        set_theme_mode(self.root, mode)

    def save_close_preference(self):
        try:
            write_config({'close_to_tray': self.close_to_tray.get()})
        except Exception:
            self.close_to_tray.set(read_config().get('close_to_tray', True))
            self.log('Neizdevās saglabāt loga aizvēršanas izvēli. Iepriekšējā izvēle saglabāta.')

    def initialize_tray(self):
        try:
            if self.tray is None:
                from tray_support import WindowsTray
                self.tray = WindowsTray(self.root, asset('logistra.ico'), self.exit_application, self.log)
        except Exception:
            self.log('System tray ikonu neizdevās izveidot. Logs paliek atvērts.')

    def restore_window(self):
        timer = getattr(self, 'startup_hide_timer', None)
        if timer is not None:
            self.root.after_cancel(timer)
            self.startup_hide_timer = None
        if self.tray is not None and self.tray.ready:
            self.tray.show()
        else:
            if self.tray is not None:
                self.tray.pending_hide = False
            self.root.deiconify()
            self.root.state('normal')
            self.root.lift()
            self.root.focus_force()

    def hide_to_tray(self):
        if sys.platform != 'win32':
            self.root.iconify()
            return
        self.initialize_tray()
        if self.tray is not None:
            try:
                self.tray.hide()
            except Exception:
                self.log('Neizdevās paslēpt logu system tray. Logs paliek atvērts.')

    def exit_application(self):
        # Tray exit bypasses the background prompt and waits for work to finish.
        super().close()

    def close(self):
        if sys.platform == 'win32':
            if not self.closing and self.close_to_tray.get():
                self.hide_to_tray()
            else:
                self.exit_application()
            return
        if self.worker and self.worker.is_alive() and not self.closing:
            destination = 'paslēpt system tray' if sys.platform == 'win32' else 'minimizēt'
            choice = messagebox.askyesnocancel('Logistra turpina drukāt', f'Turpināt darbu fonā?\n\nJā — {destination} un turpināt.\nNē — apturēt un aizvērt.', parent=self.root)
            if choice is None:
                return
            if choice:
                self.hide_to_tray()
                return
        super().close()

    def button(self, frame, text, callback):
        primary = text in ('Palaist automātiku','Saglabāt un pārbaudīt','Ielādēt sūtījumus')
        button = ttk.Button(frame, text=text, command=callback, style='Primary.TButton' if primary else 'TButton')
        button.pack(side='left', padx=(0,10))
        self.buttons.append(button)
        return button
