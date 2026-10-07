import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app_paths


class PackagedPathsTests(unittest.TestCase):
    def test_generic_defaults_win_over_local_development_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / 'bundle'
            bundle.mkdir()
            (bundle / 'config.defaults.json').write_text(json.dumps({'sender_id': '', 'printer': '', 'auto_print': False}))
            (bundle / 'config.json').write_text(json.dumps({'sender_id': '99999', 'printer': 'Personal printer'}))
            with patch.object(app_paths.sys, 'frozen', True, create=True), patch.object(app_paths.sys, '_MEIPASS', str(bundle), create=True), patch.dict(app_paths.os.environ, {'LOGISTRA_DATA_DIR': str(root / 'user-data')}):
                target = app_paths.initialize_config()
                cfg = json.loads((target / 'config.json').read_text())
                self.assertEqual(cfg['sender_id'], '')
                self.assertEqual(cfg['printer'], '')
                self.assertFalse(cfg['auto_print'])

    def test_first_run_and_updates_preserve_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / 'bundle'
            bundle.mkdir()
            (bundle / 'config.json').write_text(json.dumps({'sender_id': '12345', 'autostart': True, 'list_verified': True}))
            with patch.object(app_paths.sys, 'frozen', True, create=True), patch.object(app_paths.sys, '_MEIPASS', str(bundle), create=True), patch.dict(app_paths.os.environ, {'LOGISTRA_DATA_DIR': str(root / 'data')}):
                target = app_paths.initialize_config()
                cfg = json.loads((target / 'config.json').read_text())
                self.assertFalse(cfg['list_verified'])
                self.assertFalse(cfg['autostart'])
                (target / 'config.json').write_text('{"sender_id":"custom","printer":"TSC DA210","adobe_path":"saved","api_verified":true}')
                key = target / 'api-key.dpapi'
                key.write_bytes(b'encrypted-key-sentinel')
                history = target / 'data' / 'state.sqlite'
                history.parent.mkdir()
                history.write_bytes(b'history-sentinel')
                app_paths.initialize_config()
                cfg = json.loads((target / 'config.json').read_text())
                self.assertEqual(cfg['sender_id'], 'custom')
                self.assertEqual(cfg['printer'], 'TSC DA210')
                self.assertEqual(cfg['adobe_path'], 'saved')
                self.assertTrue(cfg['api_verified'])
                self.assertEqual(key.read_bytes(), b'encrypted-key-sentinel')
                self.assertEqual(history.read_bytes(), b'history-sentinel')
