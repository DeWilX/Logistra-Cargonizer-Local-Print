"""Check distributable macOS archives contain generic settings and no user data."""
import json
from pathlib import PurePosixPath
import stat
import sys
from zipfile import ZipFile


def audit(path):
    with ZipFile(path) as archive:
        defaults = []
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if '__MACOSX' in name.parts or name.name.startswith('._'):
                continue  # Resource forks created by ditto are not application files.
            if name.name in ('config.json', 'api-key.dpapi', 'gui.log') or name.suffix in ('.sqlite', '.sqlite3', '.db', '.dpapi'):
                raise RuntimeError(f'User data included in package: {entry.filename}')
            if name.name == 'config.defaults.json':
                if stat.S_ISLNK(entry.external_attr >> 16):
                    continue
                cfg = json.loads(archive.read(entry))
                if cfg['sender_id'] or cfg['printer'] or cfg.get('api_key') or cfg.get('pdf_directory'):
                    raise RuntimeError('Package contains nonempty account or local path defaults')
                defaults.append(entry.filename)
        if not defaults:
            raise RuntimeError('Packaged default configuration missing')
        print(f'{path}: generic account/printer defaults; no configuration, key or history files')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python audit_macos_package.py ARCHIVE.zip [...]')
    for filename in sys.argv[1:]:
        audit(filename)
