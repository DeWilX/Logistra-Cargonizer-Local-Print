"""Local Windows printer picker and PDF test print. No third-party Python packages."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tempfile
import tkinter as tk
from tkinter import filedialog, ttk

from logistra import ROOT, Client, print_pdf, shipment_id, is_pdf_export_printer, label_filename, label_identifier, download_label, pdf_directory
from ui_theme import asset


def saved_labels():
    identifiers = set()
    for directory in {pdf_directory(root=ROOT), ROOT / 'data'}:
        for file in directory.glob('*.pdf'):
            try:
                identifiers.add(label_identifier(file))
            except ValueError:
                continue
    return sorted(identifiers, key=int, reverse=True)


def label_file(cfg, identifier):
    identifier = shipment_id(identifier)
    directory = pdf_directory(cfg, ROOT)
    directory.mkdir(parents=True, exist_ok=True)
    directories = [directory] + ([ROOT / 'data'] if directory != ROOT / 'data' else [])
    candidates = [path for folder in directories for prefix in ('', 'reprint-', 'test-') for path in [*sorted(folder.glob(f'{prefix}{identifier}_*.pdf')), folder / f'{prefix}{identifier}.pdf']]
    file = next((path for path in candidates if path.is_file()), None)
    if file is None:
        file = download_label(Client(cfg), identifier, 'reprint-', directory)
    elif '_' not in file.stem:
        reference = Client(cfg).reference(identifier)
        prefix = file.stem[:-len(identifier)]
        named = directory / label_filename(identifier, reference, prefix)
        if named != file:
            if file.parent == directory:
                file.replace(named)
            else:
                save_pdf_copy(file, named)
            file = named
    if file.parent != directory:
        file = save_pdf_copy(file, directory / file.name)
    validate_pdf(str(file))
    return file


def reprint_label(cfg, identifier):
    file = label_file(cfg, identifier)
    print_pdf(cfg, file)
    # Manual reprints never change the automatic jobs database.


def save_pdf_copy(source, destination):
    source = validate_pdf(str(source))
    destination = Path(destination)
    if source.resolve() == destination.resolve():
        return destination
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.logistra-', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def export_label(cfg, identifier, destination):
    return save_pdf_copy(label_file(cfg, identifier), destination)


def default_test_pdf(cfg):
    directory = pdf_directory(cfg, ROOT)
    directory.mkdir(parents=True, exist_ok=True)
    return save_pdf_copy(asset('default-test-label.pdf'), directory / 'Logistra-testa-druka.pdf')


def choose_pdf_destination(parent, filename):
    directory = pdf_directory(root=ROOT)
    directory.mkdir(parents=True, exist_ok=True)
    return filedialog.asksaveasfilename(parent=parent, title='Saglabāt oriģinālo etiķetes PDF',
                                      initialdir=str(directory), initialfile=filename, defaultextension='.pdf',
                                      filetypes=[('PDF', '*.pdf')])


def prepare_pdf_directory(cfg, destination):
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=destination, prefix='.logistra-check-', suffix='.tmp'):
            pass
    except OSError as error:
        raise ValueError('Izvēlētajā mapē nevar izveidot failu. Izvēlies citu PDF mapi.') from error
    previous = pdf_directory(cfg, ROOT)
    if previous.resolve() != destination:
        for source in previous.glob('*.pdf'):
            target = destination / source.name
            if target.exists():
                if target.read_bytes() != source.read_bytes():
                    raise ValueError(f'Izvēlētajā mapē jau ir atšķirīgs fails: {source.name}. Izvēlies citu mapi.')
            else:
                save_pdf_copy(source, target)
    return str(destination)


def installed_printers():
    if sys.platform == 'darwin':
        result = subprocess.run(['/usr/bin/lpstat', '-p'], capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'LC_ALL': 'C'})
        if result.returncode:
            if 'No destinations added' in result.stderr:
                return []
            raise RuntimeError('Neizdevās nolasīt macOS printerus. Pārbaudi Printers & Scanners iestatījumus.')
        return sorted({line.split()[1] for line in result.stdout.splitlines() if line.startswith('printer ')}, key=str.casefold)
    if os.name != 'nt':
        raise RuntimeError('Printeru saraksts pieejams Windows datorā.')
    command = ("$ErrorActionPreference='Stop'; "
               "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding; "
               "ConvertTo-Json -Compress -InputObject @(Get-Printer | Select-Object -ExpandProperty Name)")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, timeout=30,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Neizdevās nolasīt printerus. Pārbaudi Windows Print Spooler servisu.')
    names = json.loads(result.stdout.decode('utf-8-sig'))
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise RuntimeError('Negaidīta Windows printeru saraksta atbilde.')
    return sorted(set(names), key=str.casefold)


def preferred_printer(names, current):
    if current in names:
        return current
    normalize = lambda name: ''.join(character for character in name.casefold() if character.isalnum())
    target = normalize(current)
    if not target:
        return ''
    matches = [name for name in names if normalize(name) == target]
    return matches[0] if len(matches) == 1 else ''


def save_printer(printer, executable, backend='sumatra'):
    if not printer:
        raise ValueError('Izvēlies printeri no saraksta.')
    if sys.platform != 'darwin' and not is_pdf_export_printer({'printer': printer}) and not Path(executable).is_file():
        raise ValueError('Norādi esošu PDF drukāšanas programmas EXE failu.')
    # Read latest configuration so API/discovery settings are preserved.
    path = ROOT / 'config.json'
    cfg = json.loads(path.read_text(encoding='utf-8'))
    cfg.update(printer=printer, print_backend='cups' if sys.platform == 'darwin' else backend)
    if sys.platform != 'darwin':
        cfg['adobe_path' if backend == 'adobe' else 'sumatra_path'] = executable
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return cfg


def validate_pdf(path):
    file = Path(path)
    if not file.is_file():
        raise ValueError('Izvēlies PDF failu.')
    with file.open('rb') as stream:
        if stream.read(5) != b'%PDF-':
            raise ValueError('Izvēlētais fails nav PDF.')
    return file


class PrinterWindow:
    def __init__(self, window, embedded=False, on_print=None):
        self.window = window
        self.on_print = on_print
        self.events = queue.Queue()
        self.busy = False
        self.buttons = []
        self.names = []
        cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
        self.printer = tk.StringVar(value=cfg.get('printer', ''))
        self.backend = tk.StringVar(value=cfg.get('print_backend', 'sumatra'))
        if sys.platform == 'darwin':
            self.backend.set('cups')
        self.executable = tk.StringVar(value=cfg.get('adobe_path' if self.backend.get() == 'adobe' else 'sumatra_path', ''))
        for base in [os.environ.get('LOCALAPPDATA'), os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]:
            if base and not Path(self.executable.get()).is_file():
                paths = ['Adobe/Acrobat DC/Acrobat/Acrobat.exe', 'Adobe/Acrobat Reader DC/Reader/AcroRd32.exe', 'Adobe/Reader 11.0/Reader/AcroRd32.exe'] if self.backend.get() == 'adobe' else ['SumatraPDF/SumatraPDF.exe']
                for relative in paths:
                    candidate = Path(base) / relative
                    if candidate.is_file():
                        self.executable.set(str(candidate))
                        break
        self.identifier = tk.StringVar()
        self.message = tk.StringVar(value='Nolasa Windows printerus…')
        if not embedded:
            window.title('Logistra — lokālā druka')
            window.geometry('760x650')
            window.minsize(640, 620)
        style = ttk.Style(window)
        if not embedded:
            from ui_theme import apply_theme
            apply_theme(window)
        frame = ttk.Frame(window, padding=24)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text='Printeris un PDF testa druka', font=('Segoe UI', 18, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
        ttk.Label(frame, text='Izvēlies printeri un spied “Testa print”. Iebūvēta testa lapa: 102 × 192 mm.', wraplength=670).grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 18))
        ttk.Label(frame, text='Printeris').grid(row=2, column=0, sticky='w')
        self.picker = ttk.Combobox(frame, textvariable=self.printer, state='readonly')
        self.picker.grid(row=3, column=0, sticky='ew', padx=(0, 12), pady=(5, 12))
        self.button(frame, 'Atsvaidzināt', self.refresh, 3)
        ttk.Label(frame, text='PDF drukāšanas programma (Adobe: Acrobat.exe vai AcroRd32.exe)').grid(row=4, column=0, sticky='w')
        ttk.Entry(frame, textvariable=self.executable).grid(row=5, column=0, sticky='ew', padx=(0, 12), pady=(5, 12))
        self.button(frame, 'Izvēlēties EXE', self.choose_executable, 5)
        actions = ttk.Frame(frame)
        actions.grid(row=8, column=0, columnspan=2, sticky='w', pady=(5, 14))
        for label, callback in [('Saglabāt printeri', self.save), ('Testa print', self.print_selected)]:
            button = ttk.Button(actions, text=label, command=callback)
            button.pack(side='left', padx=(0, 12))
            self.buttons.append(button)
        ttk.Separator(frame).grid(row=9, column=0, columnspan=2, sticky='ew', pady=(0, 14))
        ttk.Label(frame, text='Pādrukāt etiķeti — izvēlies saglabātu ID vai ievadi sūtījuma ID').grid(row=10, column=0, columnspan=2, sticky='w')
        self.history = ttk.Combobox(frame, textvariable=self.identifier, values=saved_labels())
        self.history.grid(row=11, column=0, sticky='ew', padx=(0, 12), pady=(5, 12))
        self.button(frame, 'Pādrukāt etiķeti', self.reprint, 11)
        ttk.Label(frame, text='Katra pādruka izdrukā vēl vienu kopiju. Microsoft Print to PDF vietā saglabā oriģinālā PDF kopiju izvēlētajā mapē; printera pārbaude netiek veikta.', wraplength=670).grid(row=12, column=0, columnspan=2, sticky='w', pady=(0, 14))
        ttk.Label(frame, textvariable=self.message, wraplength=670).grid(row=13, column=0, columnspan=2, sticky='w')
        ttk.Label(frame, text='Adobe: pirms testa iestati Actual size / 100% un vienu kopiju Reader drukas logā. Papīra izmēru iestati draiverī.', wraplength=670).grid(row=14, column=0, columnspan=2, sticky='w', pady=(12, 0))
        programs = ttk.Frame(frame)
        programs.grid(row=15, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Label(programs, text='Drukāšanas režīms: ').pack(side='left')
        selector = ttk.Combobox(programs, textvariable=self.backend, values=['adobe', 'sumatra'], state='readonly', width=14)
        selector.pack(side='left')
        selector.bind('<<ComboboxSelected>>', self.change_program)
        if sys.platform == 'darwin':
            selector.configure(values=['cups'], state='disabled')
            # Native macOS printing does not require a PDF executable picker.
            for row in (4, 5):
                for widget in frame.grid_slaves(row=row):
                    widget.grid_remove()
            for widget in frame.grid_slaves(row=14):
                widget.configure(text='macOS druka: viena kopija bez mērogošanas. Papīra izmēru iestati printera draiverī.')
        if not embedded:
            window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(100, self.receive)
        self.refresh()

    def button(self, frame, label, callback, row):
        button = ttk.Button(frame, text=label, command=callback)
        button.grid(row=row, column=1, sticky='ew', pady=(5, 12))
        self.buttons.append(button)

    def close(self):
        if self.busy:
            self.message.set('Sagaidi pašreizējās darbības pabeigšanu, tad aizver logu.')
        else:
            self.window.destroy()

    def background(self, action, callback, message):
        if self.busy:
            return
        self.busy = True
        self.message.set(message)
        for button in self.buttons:
            button.state(['disabled'])
        def run():
            try:
                self.events.put((callback, action(), None))
            except Exception as error:
                self.events.put((callback, None, str(error)))
        threading.Thread(target=run, daemon=True).start()

    def receive(self):
        try:
            callback, result, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            for button in self.buttons:
                button.state(['!disabled'])
            if error:
                self.message.set('Kļūda: ' + error)
            else:
                callback(result)
        self.window.after(100, self.receive)

    def refresh(self):
        def loaded(names):
            self.names = names
            self.history['values'] = saved_labels()
            self.picker['values'] = names
            self.printer.set(preferred_printer(names, self.printer.get()))
            self.message.set(f'Atrasti {len(names)} printeri. Izvēlies vajadzīgo.' if names else 'Printeri nav atrasti. Instalē printera draiveri un atsvaidzini sarakstu.')
        self.background(installed_printers, loaded, 'Nolasa Windows printerus…')

    def choose_executable(self):
        path = filedialog.askopenfilename(parent=self.window, title='Izvēlies Acrobat.exe, AcroRd32.exe vai SumatraPDF.exe', filetypes=[('Windows programma', '*.exe')])
        if path:
            self.executable.set(path)

    def save(self):
        try:
            if self.printer.get() not in self.names:
                raise ValueError('Izvēlies printeri no saraksta.')
            save_printer(self.printer.get(), self.executable.get(), self.backend.get())
            self.message.set('Printeris saglabāts. Ja fona skripts jau darbojas, restartē to, lai lietotu jauno izvēli.')
        except Exception as error:
            self.message.set('Kļūda: ' + str(error))

    def print_selected(self):
        try:
            if self.printer.get() not in self.names:
                raise ValueError('Izvēlies printeri no saraksta.')
            cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
            cfg.update(printer=self.printer.get(), print_backend=self.backend.get())
            cfg['adobe_path' if self.backend.get() == 'adobe' else 'sumatra_path'] = self.executable.get()
        except Exception as error:
            self.message.set('Kļūda: ' + str(error))
            return
        if is_pdf_export_printer(cfg):
            destination = choose_pdf_destination(self.window, 'Logistra-testa-druka.pdf')
            if destination:
                self.background(lambda: save_pdf_copy(asset('default-test-label.pdf'), destination), self.export_completed, 'Saglabā testa PDF…')
            return
        self.background(lambda: print_pdf(cfg, default_test_pdf(cfg)),
                        lambda _: self.print_completed(cfg),
                        'Nosūta PDF printerim…')


    def reprint(self):
        try:
            identifier = shipment_id(self.identifier.get())
            if self.printer.get() not in self.names:
                raise ValueError('Izvēlies printeri no saraksta.')
            cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
            cfg.update(printer=self.printer.get(), print_backend=self.backend.get())
            cfg['adobe_path' if self.backend.get() == 'adobe' else 'sumatra_path'] = self.executable.get()
        except Exception as error:
            self.message.set('Kļūda: ' + str(error))
            return
        if is_pdf_export_printer(cfg):
            def prepared(file):
                destination = choose_pdf_destination(self.window, file.name.removeprefix('reprint-').removeprefix('test-'))
                if destination:
                    self.background(lambda: save_pdf_copy(file, destination), self.export_completed, 'Saglabā oriģinālo PDF…')
            self.background(lambda: label_file(cfg, identifier), prepared, 'Sagatavo etiķetes PDF…')
            return
        def completed(_):
            self.history['values'] = saved_labels()
            self.message.set(f'Etiķete {identifier} atkārtoti nosūtīta Windows drukas rindai. Pārbaudi fizisko izdruku.')
            if self.on_print:
                self.on_print(cfg)
        self.background(lambda: reprint_label(cfg, identifier), completed, f'Pādrukā etiķeti {identifier}…')

    def export_completed(self, _):
        self.history['values'] = saved_labels()
        self.message.set('Oriģinālā PDF kopija saglabāta izvēlētajā mapē. Druka nav veikta; fiziskais printeris nav apstiprināts.')


    def change_program(self, _):
        cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
        self.executable.set(cfg.get('adobe_path' if self.backend.get() == 'adobe' else 'sumatra_path', ''))

    def print_completed(self, cfg):
        self.message.set('PDF nosūtīts drukas rindai. Pārbaudi fizisko etiķeti. Atkārtots klikšķis drukās vēl vienu kopiju.')
        if self.on_print:
            self.on_print(cfg)


if __name__ == '__main__':
    from app_paths import initialize_config
    initialize_config()
    window = tk.Tk()
    PrinterWindow(window)
    window.mainloop()
