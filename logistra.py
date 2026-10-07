"""Cargonizer PDF download and Windows print worker; Python 3.10+, stdlib only."""
import argparse
import contextlib
from collections import OrderedDict
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from app_paths import application_root
from network_tls import verified_context

ROOT = application_root()
BASE = 'https://api.cargonizer.no'
_api_cache = OrderedDict()
_api_cache_lock = threading.Lock()


def api_cache_ttl(path):
    endpoint = urllib.parse.urlsplit(path).path
    if endpoint == '/consignments.xml':
        return 2
    if re.fullmatch(r'/consignments/[1-9][0-9]*\.xml', endpoint):
        return 30
    return 0


def shipment_id(value):
    value = str(value).strip()
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise ValueError('Consignment ID must be a positive numeric ID, not a tracking number.')
    return str(int(value))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('API redirect refused; check the endpoint. Credentials were not forwarded.')


def api_key():
    key = os.environ.get('CARGONIZER_API_KEY', '').strip()
    if key:
        return key
    if sys.platform == 'darwin':
        from mac_support import keychain_key
        return keychain_key()
    if os.name != 'nt':
        raise RuntimeError('Set CARGONIZER_API_KEY, or run setup-key.ps1 on Windows.')
    from windows_support import read_windows_key
    return read_windows_key(ROOT / 'api-key.dpapi')


class Client:
    retry_not_before = 0
    def __init__(self, cfg):
        self.cfg = cfg
        shipment_id(cfg.get('sender_id', ''))
        self.key = api_key()
        context = verified_context()
        self.opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context))
        self.pagination = {}
        self.references = {}

    def get(self, path, fresh=False):
        if not path.startswith('/') or path.startswith('//') or '#' in path:
            raise ValueError('API path must be relative to api.cargonizer.no.')
        wait = Client.retry_not_before - time.monotonic()
        if wait > 0:
            raise RuntimeError(f'API pieprasījumu limits; nākamais mēģinājums pēc {int(wait) + 1} sekundēm.')
        ttl = api_cache_ttl(path)
        cache_key = (str(self.cfg['sender_id']), hashlib.sha256(self.key.encode()).digest(), path)
        if ttl and not fresh and not self.cfg.get('_fresh_api'):
            with _api_cache_lock:
                cached = _api_cache.get(cache_key)
                if cached and cached[0] > time.monotonic():
                    _api_cache.move_to_end(cache_key)
                    self.pagination = dict(cached[2])
                    return cached[1]
        req = urllib.request.Request(BASE + path, headers={
            'X-Cargonizer-Key': self.key,
            'X-Cargonizer-Sender': str(self.cfg['sender_id'])})
        try:
            with self.opener.open(req, timeout=45) as response:
                self.pagination = {name: response.headers.get('X-Pagination-' + name)
                                   for name in ('Total-Count', 'Total-Pages', 'Per-Page')}
                body = response.read(32 * 1024 * 1024 + 1)
                if len(body) > 32 * 1024 * 1024:
                    raise RuntimeError('API response exceeds 32 MB.')
                if ttl and len(body) <= 8 * 1024 * 1024:
                    with _api_cache_lock:
                        _api_cache[cache_key] = (time.monotonic() + ttl, body, dict(self.pagination))
                        _api_cache.move_to_end(cache_key)
                        while len(_api_cache) > 128 or sum(len(item[1]) for item in _api_cache.values()) > 8 * 1024 * 1024:
                            _api_cache.popitem(last=False)
                return body
        except urllib.error.HTTPError as error:
            if error.code == 429:
                from email.utils import parsedate_to_datetime
                try:
                    delay = float(error.headers.get('Retry-After', '60'))
                except ValueError:
                    try:
                        delay = parsedate_to_datetime(error.headers['Retry-After']).timestamp() - time.time()
                    except (ValueError, TypeError, KeyError, OverflowError):
                        delay = 60
                if not 5 <= delay <= 86400:
                    delay = 60
                Client.retry_not_before = time.monotonic() + delay
                raise RuntimeError(f'API pieprasījumu limits; pauze {int(delay)} sekundes.') from None
            raise RuntimeError(f'API HTTP {error.code}; check API key, Sender ID and endpoint.') from None

    def ids(self):
        if not self.cfg.get('list_verified') or not self.cfg.get('list_path'):
            raise RuntimeError('Automatic discovery is not configured. Verify the list endpoint and pagination first; see README.md.')
        body = self.get(self.cfg['list_path'], fresh=True)
        ids = parse_ids(body)
        for item in ET.fromstring(body).findall('consignment'):
            self.references[shipment_id(item.findtext('id') or item.get('id'))] = item.findtext('consignor-reference', '')
        pages = self.pagination.get('Total-Pages')
        count = self.pagination.get('Total-Count')
        if pages is not None and int(pages) > 1:
            raise RuntimeError('API list has multiple pages. Pagination must be configured before watching; no jobs processed.')
        if count is not None and int(count) != len(ids):
            raise RuntimeError('API list count differs from parsed IDs; no jobs processed.')
        return ids

    def pdf(self, identifier):
        query = urllib.parse.urlencode({'consignment_ids[]': shipment_id(identifier)})
        body = self.get('/consignments/label_pdf?' + query)
        if not body.startswith(b'%PDF-'):
            raise RuntimeError('API did not return a PDF. The label may not be ready yet.')
        return body

    def reference(self, identifier):
        identifier = shipment_id(identifier)
        if identifier not in self.references:
            root = ET.fromstring(self.get(f'/consignments/{identifier}.xml'))
            item = root if root.tag == 'consignment' else root.find('consignment')
            if item is None:
                raise ValueError('Cargonizer neatgrieza sūtījuma informāciju.')
            self.references[identifier] = item.findtext('consignor-reference', '')
        return self.references[identifier]


def label_filename(identifier, reference='', prefix=''):
    identifier = shipment_id(identifier)
    reference = reference if isinstance(reference, str) else ''
    reference = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', reference).strip(' .')[:100].rstrip(' .')
    return f'{prefix}{identifier}' + (f'_{reference}' if reference else '') + '.pdf'


def label_identifier(file):
    match = re.fullmatch(r'(?:test-|reprint-)?([1-9][0-9]*)(?:_.+)?', Path(file).stem)
    if not match:
        raise ValueError('Not a saved shipment label.')
    return shipment_id(match[1])


def pdf_directory(cfg=None, root=None):
    root = Path(root) if root is not None else ROOT
    if cfg is None:
        config = root / 'config.json'
        cfg = json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
    value = cfg.get('pdf_directory', '')
    if not value:
        return root / 'data'
    directory = Path(value).expanduser()
    if not directory.is_absolute():
        raise ValueError('PDF mapes ceļam jābūt pilnam ceļam.')
    return directory


def find_label(identifier, prefixes=('', 'reprint-', 'test-'), directory=None):
    identifier = shipment_id(identifier)
    directory = Path(directory) if directory is not None else pdf_directory()
    for prefix in prefixes:
        files = sorted(directory.glob(f'{prefix}{identifier}_*.pdf'))
        legacy = directory / f'{prefix}{identifier}.pdf'
        if files:
            return files[0]
        if legacy.is_file():
            return legacy
    return None


def download_label(client, identifier, prefix='', directory=None):
    body = client.pdf(identifier)
    cfg = getattr(client, 'cfg', None)
    directory = Path(directory) if directory is not None else pdf_directory(cfg if isinstance(cfg, dict) else None)
    file = directory / label_filename(identifier, client.reference(identifier), prefix)
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_suffix('.download.tmp')
    temporary.write_bytes(body)
    temporary.replace(file)
    return file


def parse_ids(body):
    root = ET.fromstring(body)
    if root.tag != 'consignments':
        raise ValueError('Expected a <consignments> XML response.')
    ids = set()
    for item in root.findall('consignment'):
        value = item.findtext('id') or item.get('id')
        if not value:
            raise ValueError('Consignment is missing its numeric ID; verify the list response schema.')
        ids.add(shipment_id(value))
    return sorted(ids, key=int)


@contextlib.contextmanager
def single_worker():
    directory = ROOT / 'data'
    directory.mkdir(exist_ok=True)
    with (directory / 'worker.lock').open('a+b') as file:
        file.seek(0)
        file.write(b'0')
        file.flush()
        file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another Logistra worker is already running.') from None
        yield


def database():
    db = sqlite3.connect(ROOT / 'data' / 'state.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT)')
    db.commit()
    return db


def status(db, identifier, value):
    db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?)', (identifier, value))
    db.commit()


def pdf_executable(cfg):
    if sys.platform == 'darwin':
        return Path('/usr/bin/lp')
    backend = cfg.get('print_backend', 'sumatra')
    if backend not in ('sumatra', 'adobe'):
        raise RuntimeError('Unknown PDF printing program.')
    return Path(cfg.get('adobe_path' if backend == 'adobe' else 'sumatra_path', ''))


def is_pdf_export_printer(cfg):
    return str(cfg.get('printer', '')).strip().casefold() == 'microsoft print to pdf'


def print_pdf(cfg, file):
    if sys.platform == 'darwin':
        if not cfg.get('printer'):
            raise RuntimeError('Select a macOS printer first.')
        result = subprocess.run(['/usr/bin/lp', '-d', cfg['printer'], '-n', '1', '-o', 'sides=one-sided',
                                 '-o', 'print-scaling=none', str(file.resolve())],
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError('macOS print submission failed. Check the printer queue before retrying.')
        return
    if os.name != 'nt':
        raise RuntimeError('Physical printing requires Windows.')
    if not cfg.get('printer'):
        raise RuntimeError('Set the Windows printer name in config.json first.')
    if is_pdf_export_printer(cfg):
        raise RuntimeError('Microsoft Print to PDF: saglabā oriģinālo PDF manuāli lietotnē. Automātiskai drukai izvēlies fizisku printeri.')
    executable = pdf_executable(cfg)
    if not executable.is_file():
        raise RuntimeError('PDF printing program was not found; choose its EXE in the printer settings.')
    if cfg.get('print_backend', 'sumatra') == 'adobe':
        command = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding; "
                   "$p=Get-Printer -Name $env:LOGISTRA_PRINTER; "
                   "if (!$p) { throw 'Printer not found' }; $p | Select-Object Name,DriverName,PortName | ConvertTo-Json -Compress")
        details = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                 env={**os.environ, 'LOGISTRA_PRINTER': cfg['printer']},
                                 capture_output=True, timeout=30,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if details.returncode:
            raise RuntimeError('Cannot read printer driver and port for Adobe printing.')
        printer = json.loads(details.stdout.decode('utf-8-sig'))
        arguments = [str(executable), '/t', str(file.resolve()), printer['Name'], printer['DriverName'], printer['PortName']]
    else:
        arguments = [str(executable), '-print-to', cfg['printer'], '-print-settings', cfg['print_settings'], '-silent', str(file.resolve())]
    result = subprocess.run(arguments, timeout=90,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(f'PDF print command failed, exit code {result.returncode}. Check the Windows queue before retrying.')


def process(db, client, cfg, identifier, printing=False):
    identifier = shipment_id(identifier)
    if printing and is_pdf_export_printer(cfg):
        raise RuntimeError('Microsoft Print to PDF izmanto manuālai PDF saglabāšanai. Automātiskai drukai izvēlies fizisku printeri.')
    row = db.execute('SELECT status FROM jobs WHERE id=?', (identifier,)).fetchone()
    if row and row[0] in ('baseline', 'submitted', 'uncertain', 'submitting'):
        return
    directory = pdf_directory(cfg)
    file = find_label(identifier, ('',), directory)
    if file is None or not row:
        file = download_label(client, identifier, directory=directory)
        status(db, identifier, 'downloaded')
        print(f'Downloaded PDF: {identifier}', flush=True)
    if printing:
        # Persist before submission: a crash or timeout must not silently duplicate a label.
        status(db, identifier, 'submitting')
        try:
            print_pdf(cfg, file)
        except Exception:
            status(db, identifier, 'uncertain')
            raise
        status(db, identifier, 'submitted')
        print(f'Sent to print queue: {identifier}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'probe-list', 'baseline', 'watch', 'download', 'test-print', 'status'])
    parser.add_argument('--id', help='Numeric Cargonizer consignment ID')
    parser.add_argument('--path', help='API path for read-only list probe, e.g. /consignments.xml')
    parser.add_argument('--print', dest='printing', action='store_true', help='Enable local printing in watch mode')
    args = parser.parse_args()
    from app_paths import initialize_config
    initialize_config()
    cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    with single_worker(), contextlib.closing(database()) as db:
        if args.command == 'status':
            for identifier, state in db.execute('SELECT id, status FROM jobs ORDER BY CAST(id AS INTEGER)'):
                print(identifier, state)
            return
        if args.command in ('download', 'test-print') and not args.id:
            parser.error('--id is required')
        if args.command == 'test-print' or args.printing:
            if (os.name != 'nt' and sys.platform != 'darwin') or not cfg.get('printer') or not pdf_executable(cfg).is_file():
                raise RuntimeError('Configure printer and PDF printing program on Windows before printing.')
        client = Client(cfg)
        if args.command == 'check':
            root = ET.fromstring(client.get('/transport_agreements.xml'))
            if root.tag != 'transport-agreements':
                raise RuntimeError('Unexpected API response.')
            print(f'API access OK for Sender ID {cfg["sender_id"]}.')
        elif args.command == 'probe-list':
            ids = parse_ids(client.get(args.path or '/consignments.xml'))
            print(f'List response parsed: {len(ids)} consignments. Pagination and freshness still need verification.')
            for name, value in client.pagination.items():
                print(f'X-Pagination-{name}: {value if value is not None else "not provided"}')
        elif args.command == 'baseline':
            ids = client.ids()
            if db.execute("SELECT 1 FROM settings WHERE name='baseline'").fetchone():
                raise RuntimeError('Baseline already exists; it will not be overwritten.')
            with db:
                db.executemany('INSERT OR IGNORE INTO jobs VALUES (?, ?)', [(i, 'baseline') for i in ids])
                db.execute("INSERT INTO settings VALUES ('baseline', 'yes')")
            print(f'Baseline saved: {len(ids)} existing shipments will not be automatically printed.')
        elif args.command == 'download':
            process(db, client, cfg, args.id)
        elif args.command == 'test-print':
            # Explicit repeatable test; does not mark the automatic shipment job as printed.
            identifier = shipment_id(args.id)
            file = download_label(client, identifier, 'test-')
            print_pdf(cfg, file)
            print('Test label sent to print queue. Verify the physical label.')
        elif args.command == 'watch':
            if not db.execute("SELECT 1 FROM settings WHERE name='baseline'").fetchone():
                raise RuntimeError('Run baseline first, after verifying the list API.')
            interval = max(5, int(cfg['poll_seconds']))
            print('Watching. Ctrl+C stops. Printing: ' + str(args.printing), flush=True)
            while True:
                try:
                    ids = set(client.ids())
                    ids.update(i for i, in db.execute("SELECT id FROM jobs WHERE status='downloaded'"))
                    for identifier in sorted(ids, key=int):
                        try:
                            process(db, client, cfg, identifier, args.printing)
                        except Exception as error:
                            print(f'Job {identifier}: {error}', flush=True)
                except Exception as error:
                    print(f'Poll failed: {error}', flush=True)
                time.sleep(interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped.')
    except Exception as error:
        print(f'Error: {error}')
        raise SystemExit(1)
