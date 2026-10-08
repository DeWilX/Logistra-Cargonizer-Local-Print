"""Browse live Cargonizer shipments using the two endpoints verified in-session."""
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from logistra import Client, shipment_id
from ui_theme import asset, theme_color
from localization import translate
from tooltips import Tooltip

PERIOD_PRESETS = ('Šodien', 'Pēdējās 7 dienas', 'Pēdējās 30 dienas', 'Šonedēļ',
                  'Pagājušajā nedēļā', 'Šomēnes', 'Pagājušajā mēnesī', 'Šogad',
                  'Pagājušajā gadā', 'Visi datumi', 'Pielāgots periods')


def preset_period(name, today=None):
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    periods = {
        'Šodien': (today, today),
        'Pēdējās 7 dienas': (today - timedelta(days=6), today),
        'Pēdējās 30 dienas': (today - timedelta(days=29), today),
        'Šonedēļ': (monday, today),
        'Pagājušajā nedēļā': (monday - timedelta(days=7), monday - timedelta(days=1)),
        'Šomēnes': (month_start, today),
        'Pagājušajā mēnesī': (previous_month_end.replace(day=1), previous_month_end),
        'Šogad': (today.replace(month=1, day=1), today),
        'Pagājušajā gadā': (date(today.year-1, 1, 1), date(today.year-1, 12, 31)),
        'Visi datumi': (None, None),
    }
    return periods[name]


def fit_column_widths(available, minimums):
    widths = dict(minimums)
    extra = max(0, available - sum(widths.values()))
    weights = {'recipient':3, 'address':3, 'carrier':1, 'product':2, 'reference':3, 'number':3, 'status':1}
    total = sum(weights.values())
    allocated = 0
    for name, weight in weights.items():
        addition = extra * weight // total
        widths[name] += addition
        allocated += addition
    widths['recipient'] += extra - allocated
    return widths


def parse_shipments(body):
    root = ET.fromstring(body)
    if root.tag != 'consignments':
        raise ValueError('Cargonizer neatgrieza sūtījumu sarakstu.')
    rows = []
    for item in root.findall('consignment'):
        recipient = item.find("addresses/address[@type='ConsigneeAddress']")
        created = item.findtext('created-at', '')
        address = ''
        if recipient is not None:
            country = recipient.findtext('country', '')
            postcode = recipient.findtext('postcode', '')
            city = recipient.findtext('city', '')
            address = ((country + '-' if country else '') + postcode + ' ' + city).strip()
        pieces = item.findall('bundles/bundle/pieces/piece')
        amount = len(pieces)
        if not amount:
            amount = sum(int(bundle.findtext('amount', '1')) for bundle in item.findall('bundles/bundle'))
        rows.append({'id': shipment_id(item.findtext('id') or item.get('id')),
                     'state': item.findtext('state', ''), 'created': created,
                     'carrier': item.findtext('transport-agreement/carrier/name', ''),
                     'recipient': recipient.findtext('name', '') if recipient is not None else '',
                     'address': address, 'product': item.findtext('product/name', ''), 'items': amount,
                     'reference': item.findtext('consignor-reference', ''),
                     'number': item.findtext('number-with-checksum') or item.findtext('number', '')})
    return rows


def parse_date_range(start, end):
    start = datetime.strptime(start.strip(), '%d.%m.%Y').date() if start.strip() else None
    end = datetime.strptime(end.strip(), '%d.%m.%Y').date() if end.strip() else None
    if start and end and start > end:
        raise ValueError('Sākuma datumam jābūt pirms beigu datuma.')
    return start, end


def load_shipments(cfg, view='Visi', start=None, end=None, progress=None, fresh=False):
    if start and end and start > end:
        raise ValueError('Sākuma datumam jābūt pirms beigu datuma.')
    client = Client({**cfg, '_fresh_api': True} if fresh else cfg)
    query = {'page': 1, 'per_page': 100}
    if view == 'Visi':
        query['state[]'] = 'all'
    elif view == 'Nosūtītie':
        query['state'] = 'transferred'
    if start:
        query['from'] = start.isoformat()
    if end:
        query['to'] = end.isoformat()
    records = {}
    expected = None
    page = 1
    while True:
        query['page'] = page
        rows = parse_shipments(client.get('/consignments.xml?' + urlencode(query)))
        try:
            pages = int(client.pagination['Total-Pages'])
            count = int(client.pagination['Total-Count'])
        except (TypeError, ValueError, KeyError):
            raise ValueError('API neatgrieza derīgu lapu un sūtījumu skaitu; pilnu sarakstu nevar apstiprināt.') from None
        if pages < 0 or count < 0 or pages > 1000 or (pages == 0 and count != 0):
            raise ValueError('API lapošanas dati nav derīgi.')
        if expected is None:
            expected = (pages, count)
        elif expected != (pages, count):
            raise ValueError('Sūtījumu saraksts ielādes laikā mainījās. Ielādē periodu vēlreiz.')
        if not rows and count:
            raise ValueError('API atgrieza tukšu lapu pirms saraksta beigām.')
        for row in rows:
            if row['id'] in records:
                raise ValueError('API atkārto sūtījumu vairākās lapās; pilnu sarakstu nevar apstiprināt.')
            records[row['id']] = row
        if progress:
            progress(f'Ielādē sūtījumus: lapa {page} no {max(1, pages)}, {len(records)} no {count}.')
        if page >= pages:
            break
        page += 1
    if len(records) != count:
        raise ValueError('Sūtījumu saraksts ir nepilns. Ielādē periodu vēlreiz.')
    return sorted(records.values(), key=lambda row: (row['created'], int(row['id'])), reverse=True)


def filter_shipments(rows, carrier='Visi pārvadātāji', search='', start=None, end=None):
    if start and end and start > end:
        raise ValueError('Sākuma datumam jābūt pirms beigu datuma.')
    result = []
    for row in rows:
        if carrier != 'Visi pārvadātāji' and row['carrier'] != carrier:
            continue
        if search.strip().casefold() not in ' '.join([row['id'], row['recipient'], row.get('address', ''), row['reference'], row['number']]).casefold():
            continue
        if start or end:
            try:
                created = datetime.fromisoformat(row['created'].replace('Z', '+00:00')).astimezone().date()
            except ValueError:
                continue
            if start and created < start or end and created > end:
                continue
        result.append(row)
    return result


class ShipmentBrowser:
    def __init__(self, parent, app):
        self.app = app
        self.rows = []
        self.load_succeeded = None
        self.render_after = None
        self.filter_after = None
        self.loaded_view = 'Visi'
        self.loaded_period = None
        self.view = tk.StringVar(value='Visi')
        self.carrier = tk.StringVar(value='Visi pārvadātāji')
        self.search = tk.StringVar()
        self.period = tk.StringVar(value='Pēdējās 30 dienas')
        self.setting_preset = False
        self.start_date = tk.StringVar(value=(date.today() - timedelta(days=29)).strftime('%d.%m.%Y'))
        self.end_date = tk.StringVar(value=date.today().strftime('%d.%m.%Y'))
        self.notice = tk.StringVar(value='Ielādē sūtījumus no Cargonizer. Izvēlētais sūtījums būs pieejams PDF lejupielādei un pādrukai.')
        self.filter_info = tk.StringVar(value='Filtri attiecas uz ielādētajiem sūtījumiem un to izveides datumu.')
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x')
        for label in ('Visi', 'Atvērtie', 'Nosūtītie'):
            ttk.Radiobutton(toolbar, text=label, value=label, variable=self.view, command=self.load, style='Compact.TRadiobutton').pack(side='left', padx=(0, 6))
        self.carriers = ttk.Combobox(toolbar, textvariable=self.carrier, values=['Visi pārvadātāji'], state='readonly', width=20, style='Compact.TCombobox')
        self.carriers.pack(side='left', padx=(6, 12))
        self.carriers.bind('<<ComboboxSelected>>', lambda _: self.render())
        period_box = ttk.Frame(toolbar)
        period_box.pack(side='left', padx=(8, 0))
        ttk.Label(period_box, text='Periods').pack(side='left', padx=(0, 8))
        preset_picker = ttk.Combobox(period_box, textvariable=self.period, values=PERIOD_PRESETS,
                                    state='readonly', width=22, style='Compact.TCombobox')
        preset_picker.pack(side='left')
        preset_picker.bind('<<ComboboxSelected>>', self.choose_period)
        search_box = ttk.Frame(parent)
        search_box.pack(fill='x', pady=6)
        ttk.Label(search_box, text='Meklēt').pack(side='left', padx=(0, 8))
        search_entry = ttk.Entry(search_box, textvariable=self.search, width=22, style='Compact.TEntry')
        search_entry.pack(side='left', padx=(0, 14))
        ttk.Label(search_box, text='No').pack(side='left', padx=(0, 5))
        start_entry = ttk.Entry(search_box, textvariable=self.start_date, width=11, style='Compact.TEntry')
        start_entry.pack(side='left', padx=(0, 8))
        ttk.Button(search_box, text='▦', width=2, style='Compact.TButton', command=lambda: self.open_calendar(start_entry, self.start_date)).pack(side='left', padx=(0, 8))
        ttk.Label(search_box, text='Līdz').pack(side='left', padx=(0, 5))
        end_entry = ttk.Entry(search_box, textvariable=self.end_date, width=11, style='Compact.TEntry')
        end_entry.pack(side='left', padx=(0, 8))
        self.date_entries = ((start_entry, self.start_date), (end_entry, self.end_date))
        self.valid_dates = {str(self.start_date): self.start_date.get(), str(self.end_date): self.end_date.get()}
        for entry, variable in self.date_entries:
            entry.configure(validate='key', validatecommand=(entry.register(
                lambda proposed, variable=variable: self.validate_date_input(variable, proposed)), '%P'))
            entry.bind('<FocusOut>', lambda _, variable=variable: self.commit_date(variable))
        ttk.Button(search_box, text='▦', width=2, style='Compact.TButton', command=lambda: self.open_calendar(end_entry, self.end_date)).pack(side='left', padx=(0, 8))
        for entry in (search_entry, start_entry, end_entry):
            entry.bind('<Return>', lambda _: self.apply_filters())
        ttk.Button(search_box, text='Filtrēt', command=self.apply_filters, style='Compact.TButton').pack(side='left', padx=(0, 8))
        ttk.Button(search_box, text='Notīrīt filtrus', command=self.clear, style='Compact.TButton').pack(side='left')
        controls = ttk.Frame(parent)
        controls.pack(fill='x', pady=(0, 6))
        app.button(controls, 'Ielādēt sūtījumus', lambda: self.load(fresh=True))
        app.button(controls, 'Lejupielādēt PDF', lambda: self.selected_action(app.download))
        app.button(controls, 'Pādrukāt etiķeti', lambda: self.selected_action(app.quick_reprint))
        ttk.Button(controls, text='Atvērt PDF mapi', command=app.open_folder).pack(side='left', padx=(0, 10))
        for button in controls.winfo_children():
            button.configure(style='Compact.Primary.TButton' if button.cget('style') == 'Primary.TButton' else 'Compact.TButton')
        help_label = ttk.Button(controls, text='Palīdzība', style='Compact.TButton',
                                command=lambda: messagebox.showinfo(translate(parent, 'Palīdzība'),
                                                                    translate(parent, help_text.get()), parent=parent))
        help_label.pack(side='right')
        help_text = tk.StringVar(master=parent)
        def update_help(*_):
            help_text.set(self.filter_info.get() + '\n\n' + 'Ctrl: atlasīt atsevišķus sūtījumus. Shift: atlasīt rindu diapazonu. Datumi: dd.mm.gggg. Ielāde neko nedrukā.')
        self.filter_info.trace_add('write', update_help)
        update_help()
        self.filter_tooltip = Tooltip((help_label,), help_text)
        footer = ttk.Frame(parent)
        footer.pack(side='bottom', fill='x', pady=(4, 0))
        notice_label = ttk.Label(footer, textvariable=self.notice, wraplength=1000)
        notice_label.pack(anchor='w')
        footer.bind('<Configure>', lambda event: notice_label.configure(wraplength=max(200, event.width)))
        grid = ttk.Frame(parent)
        grid.pack(fill='both', expand=True)
        grid.columnconfigure(0, weight=1)
        grid.rowconfigure(0, weight=1)
        self.action_image = tk.PhotoImage(file=str(asset('row-actions.png')))
        self.table = ttk.Treeview(grid, columns=('recipient', 'address', 'carrier', 'product', 'reference', 'items', 'date', 'number', 'status'), show='tree headings', selectmode='extended')
        self.table.heading('#0', text='PDF / Druka')
        self.table.column('#0', width=118, minwidth=118, stretch=False, anchor='center')
        self.column_minimums = {'#0':118}
        for name, label, width in [('recipient','Saņēmējs',170), ('address','Adrese',160), ('carrier','Pārvadātājs',130), ('product','Produkts',120), ('reference','Ref.',160), ('items','Pakas',75), ('date','Datums',110), ('number','Sūtījuma numurs',185), ('status','Statuss',95)]:
            self.column_minimums[name] = width
            self.table.heading(name, text=label)
            self.table.column(name, width=width, minwidth=width, stretch=False, anchor='center' if name in ('pdf', 'print', 'items', 'date') else 'w')
        self.table.grid(row=0, column=0, sticky='nsew')
        horizontal = ttk.Scrollbar(grid, orient='horizontal', command=self.table.xview)
        vertical = ttk.Scrollbar(grid, orient='vertical', command=self.table.yview)
        horizontal.grid(row=1, column=0, sticky='ew')
        vertical.grid(row=0, column=1, sticky='ns')
        self.table.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.update_theme()
        parent.winfo_toplevel().bind('<<LogistraThemeChanged>>', lambda _: self.update_theme(), add='+')
        self.table.bind('<<TreeviewSelect>>', self.select)
        self.table.bind('<ButtonRelease-1>', self.row_action)
        self.table.bind('<Motion>', self.hover_action)
        self.table.bind('<Leave>', lambda _: self.table.configure(cursor=''))
        self.table.bind('<Configure>', self.resize_columns)
        self.search.trace_add('write', self.schedule_filter)
        for variable in (self.start_date, self.end_date):
            variable.trace_add('write', self.dates_changed)

    def dates_changed(self, *_):
        if not self.setting_preset:
            self.period.set('Pielāgots periods')
        self.schedule_filter()

    def validate_date_input(self, variable, proposed):
        if len(proposed) < 10 and all(char.isdigit() or char == '.' for char in proposed):
            return True
        try:
            parse_date_range(proposed if variable is self.start_date else self.start_date.get(),
                             proposed if variable is self.end_date else self.end_date.get())
            if len(proposed) != 10:
                raise ValueError
        except ValueError:
            self.notice.set('Nederīgs datumu diapazons: ievadi dd.mm.gggg; sākums nedrīkst būt pēc beigām.')
            return False
        return True

    def commit_date(self, variable):
        try:
            parse_date_range(self.start_date.get(), self.end_date.get())
        except ValueError:
            variable.set(self.valid_dates[str(variable)])
            self.notice.set('Nederīgs datumu diapazons: ievadi dd.mm.gggg; sākums nedrīkst būt pēc beigām.')
            return
        self.valid_dates.update({str(value): value.get() for _, value in self.date_entries})

    def open_calendar(self, entry, variable):
        from date_picker import DatePicker
        self.commit_date(variable)
        start, end = parse_date_range(self.start_date.get(), self.end_date.get())
        DatePicker(entry, variable, minimum=start if variable is self.end_date else None,
                   maximum=end if variable is self.start_date else None)

    def choose_period(self, _=None):
        name = self.period.get()
        if name == 'Pielāgots periods':
            return
        start, end = preset_period(name)
        self.setting_preset = True
        try:
            self.start_date.set(start.strftime('%d.%m.%Y') if start else '')
            self.end_date.set(end.strftime('%d.%m.%Y') if end else '')
        finally:
            self.setting_preset = False
        self.apply_filters()

    def schedule_filter(self, *_):
        if self.filter_after is not None:
            self.table.after_cancel(self.filter_after)
        self.filter_info.set('Pārrēķina filtrus…')
        self.filter_after = self.table.after(400, self.render)

    def update_theme(self):
        for tag, background in [('even', '#f4f7fc'), ('odd', '#ffffff')]:
            self.table.tag_configure(tag, background=theme_color(self.table, background), foreground=theme_color(self.table, '#243247'))

    def load(self, fresh=False):
        from logistra_gui import read_config
        if self.app.task_busy:
            self.view.set(self.loaded_view)
            return
        view = self.view.get()
        try:
            start, end = parse_date_range(self.start_date.get(), self.end_date.get())
        except ValueError:
            self.render()
            return
        cfg = read_config()
        self.notice.set('Ielādē sūtījumus…')
        def action():
            try:
                progress = lambda message: self.app.events.put(('log', message))
                return load_shipments(cfg, view, start, end, progress, fresh=fresh), None
            except Exception as error:
                return None, str(error)
        def completed(result):
            rows, error = result
            if error:
                self.load_succeeded = False
                self.view.set(self.loaded_view)
                self.notice.set('Ielāde neizdevās: ' + error)
                self.app.log('Sūtījumu ielāde neizdevās: ' + error)
                return
            self.loaded_view = view
            self.load_succeeded = True
            self.loaded_period = (start, end)
            self.rows = rows
            carriers = sorted({row['carrier'] for row in rows if row['carrier']})
            self.carriers['values'] = ['Visi pārvadātāji'] + carriers
            if self.carrier.get() not in self.carriers['values']:
                self.carrier.set('Visi pārvadātāji')
            self.render()
            self.app.log(f'No Cargonizer ielādēti {len(rows)} sūtījumi. Nekas netika izdrukāts.')
        self.app.task(action, completed)

    def apply_filters(self):
        try:
            period = parse_date_range(self.start_date.get(), self.end_date.get())
        except ValueError:
            self.render()
            return
        if period != self.loaded_period:
            self.load()
        else:
            self.render()

    def render(self):
        if self.render_after is not None:
            self.table.after_cancel(self.render_after)
            self.render_after = None
        if self.filter_after is not None:
            self.table.after_cancel(self.filter_after)
            self.filter_after = None
        try:
            start, end = parse_date_range(self.start_date.get(), self.end_date.get())
            rows = filter_shipments(self.rows, self.carrier.get(), self.search.get(), start, end)
        except ValueError:
            self.filter_info.set('Nederīgs datumu diapazons: ievadi dd.mm.gggg; sākums nedrīkst būt pēc beigām.')
            self.notice.set(self.filter_info.get())
            return
        self.valid_dates.update({str(value): value.get() for _, value in self.date_entries})
        self.table.delete(*self.table.get_children())
        states = {'open': translate(self.table, 'Atvērts'), 'transferred': translate(self.table, 'Nosūtīts')}
        def insert_batch(start_index=0):
            self.render_after = None
            end_index = min(start_index + 100, len(rows))
            for index in range(start_index, end_index):
                row = rows[index]
                try:
                    display_date = datetime.fromisoformat(row['created'].replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y')
                except ValueError:
                    display_date = '—'
                self.table.insert('', 'end', iid=row['id'], image=self.action_image, values=(row['recipient'], row['address'], row['carrier'], row['product'], row['reference'], row['items'], display_date, row['number'], states.get(row['state'], row['state'])), tags=('even' if index % 2 == 0 else 'odd',))
            if end_index < len(rows):
                self.render_after = self.table.after(1, lambda: insert_batch(end_index))
        insert_batch()
        self.notice.set(f'Rāda {len(rows)} no {len(self.rows)} ielādētajiem sūtījumiem. Izvēlies sūtījumu, lai lejupielādētu vai pādrukātu etiķeti.')
        dates = []
        for row in self.rows:
            try:
                dates.append(datetime.fromisoformat(row['created'].replace('Z', '+00:00')).astimezone().date())
            except ValueError:
                pass
        period = f'{start.strftime("%d.%m.%Y") if start else "bez sākuma"} – {end.strftime("%d.%m.%Y") if end else "bez beigām"}'
        available = f' Ielādēto sūtījumu datumi: {min(dates):%d.%m.%Y} – {max(dates):%d.%m.%Y}.' if dates else ''
        reload_hint = ' Periods mainīts — nospied “Filtrēt” vai “Ielādēt sūtījumus”, lai ielādētu tā vēsturi.' if self.loaded_period != (start, end) else ' Visas izvēlētā perioda lapas ielādētas.'
        self.filter_info.set(f'Izveides datuma filtrs: {period}. Rāda {len(rows)} no {len(self.rows)}.{available}{reload_hint}')

    def clear(self):
        self.carrier.set('Visi pārvadātāji')
        self.search.set('')
        self.start_date.set('')
        self.end_date.set('')
        self.period.set('Visi datumi')
        self.render()

    def select(self, _):
        selected = self.table.selection()
        if selected:
            self.app.identifier.set(selected[0])
            self.app.printer_ui.identifier.set(selected[0])

    def selected_action(self, action):
        selected = self.table.selection()
        if not selected:
            self.notice.set('Vispirms izvēlies sūtījumu tabulā.')
            return
        self.select(None)
        if len(selected) == 1:
            action()
        else:
            action(identifiers=list(selected))

    def row_action(self, event):
        if self.app.task_busy or event.state & 0x0005:
            return
        row = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if not row:
            return
        if column == '#0':
            self.table.selection_set(row)
            self.select(None)
            box = self.table.bbox(row, '#0')
            if box:
                relative = event.x - box[0]
                self.selected_action(self.app.download if relative < box[2] / 2 else self.app.quick_reprint)

    def hover_action(self, event):
        actionable = self.table.identify_row(event.y) and self.table.identify_column(event.x) == '#0' and not self.app.task_busy
        self.table.configure(cursor='hand2' if actionable else '')

    def resize_columns(self, event):
        for name, width in fit_column_widths(max(0, event.width - 4), self.column_minimums).items():
            self.table.column(name, width=width)
