"""Keep mutable application files outside the packaged executable/app bundle."""
import json
import os
from pathlib import Path
import sys


def application_root():
    if not getattr(sys, 'frozen', False):
        return Path(__file__).resolve().parent
    if os.environ.get('LOGISTRA_DATA_DIR'):
        return Path(os.environ['LOGISTRA_DATA_DIR']).expanduser().resolve()
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/Logistra'
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Logistra'


def initialize_config():
    root = application_root()
    root.mkdir(parents=True, exist_ok=True)
    config = root / 'config.json'
    if not config.exists():
        bundle = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        bundled = bundle / 'config.defaults.json'
        if not bundled.is_file():
            bundled = bundle / 'config.json'
        values = json.loads(bundled.read_text(encoding='utf-8'))
        values.update(list_verified=False, autostart=False, auto_print=False)
        config.write_text(json.dumps(values, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return root
