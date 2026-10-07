"""Version supplied by release builds; never contains user configuration."""
import json
from pathlib import Path
import sys

VERSION = '0.1.6'
UPDATE_REPOSITORY = 'DeWilX/Logistra-Cargonizer-Local-Print'
metadata = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'release-info.json'
if metadata.is_file():
    values = json.loads(metadata.read_text(encoding='utf-8'))
    VERSION = values['version']
    UPDATE_REPOSITORY = values.get('repository', '')
