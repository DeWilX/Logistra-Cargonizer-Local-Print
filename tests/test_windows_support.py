import os
from pathlib import Path
import tempfile
import unittest

from windows_support import read_windows_key, save_windows_key


@unittest.skipUnless(os.name == 'nt', 'Requires real Windows DPAPI')
class WindowsKeyTests(unittest.TestCase):
    def test_roundtrip_encrypted_and_atomic_update(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api-key.dpapi'
            save_windows_key(path, ' first-test-key-ā ')
            self.assertEqual(read_windows_key(path), 'first-test-key-ā')
            self.assertNotIn(b'first-test-key', path.read_bytes())
            save_windows_key(path, 'second-test-key')
            self.assertEqual(read_windows_key(path), 'second-test-key')
            self.assertFalse(path.with_suffix('.dpapi.tmp').exists())

    def test_legacy_utf16_and_utf8_bom_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api-key.dpapi'
            save_windows_key(path, 'legacy-test-value')
            text = path.read_text(encoding='ascii')
            for encoding in ['utf-16', 'utf-8-sig']:
                path.write_text(text, encoding=encoding)
                self.assertEqual(read_windows_key(path), 'legacy-test-value')

    def test_corrupt_key_is_reported_without_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api-key.dpapi'
            path.write_text('invalid-secret-value')
            with self.assertRaises(RuntimeError) as raised:
                read_windows_key(path)
            self.assertNotIn('invalid-secret-value', str(raised.exception))

    def test_empty_key_does_not_replace_existing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api-key.dpapi'
            save_windows_key(path, 'preserved-test-key')
            with self.assertRaises(ValueError):
                save_windows_key(path, ' ')
            self.assertEqual(read_windows_key(path), 'preserved-test-key')
