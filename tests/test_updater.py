import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
import updater


class UpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[1] / 'build').mkdir(exist_ok=True)

    repository = 'example/logistra'
    body = b'MZ' + b'fake executable for download validation'

    def payload(self):
        return {'tag_name': 'v1.2.0', 'draft': False, 'prerelease': False, 'assets': [{
            'name': 'Logistra-Print.exe', 'state': 'uploaded', 'size': len(self.body),
            'digest': 'sha256:' + hashlib.sha256(self.body).hexdigest(),
            'browser_download_url': 'https://github.com/example/logistra/releases/download/v1.2.0/Logistra-Print.exe'}]}

    def test_version_order_and_repository_validation(self):
        self.assertEqual(updater.repository_name('https://github.com/example/logistra.git'), self.repository)
        self.assertGreater(updater.version_tuple('v1.10.0'), updater.version_tuple('1.9.9'))
        for value in ['http://github.com/example/logistra', '../repo', 'example/repo/other', 'example/repo;cmd']:
            with self.assertRaises(ValueError):
                updater.repository_name(value)

    def test_old_or_prerelease_is_not_installed(self):
        self.assertIsNone(updater.validate_release(self.payload(), self.repository, '2.0.0'))
        payload = self.payload()
        payload['prerelease'] = True
        self.assertIsNone(updater.validate_release(payload, self.repository))

    def test_wrong_repository_missing_digest_and_oversized_asset_are_rejected(self):
        for field, value in [('digest', ''), ('size', updater.MAX_EXE_SIZE+1),
                             ('browser_download_url', 'https://github.com/other/repo/releases/download/v1.2.0/Logistra-Print.exe')]:
            payload = self.payload()
            payload['assets'][0][field] = value
            with self.assertRaises(ValueError):
                updater.validate_release(payload, self.repository)

    def test_verified_download_and_failed_download_cleanup(self):
        release = updater.validate_release(self.payload(), self.repository)
        with tempfile.TemporaryDirectory() as folder:
            opener = Mock()
            opener.open.return_value = io.BytesIO(self.body)
            file = updater.download_release(release, folder, opener)
            self.assertEqual(file.read_bytes(), self.body)
            opener.open.return_value = io.BytesIO(b'MZ' + b'x' * (len(self.body)-2))
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                updater.download_release(release, folder, opener)
            self.assertEqual(file.read_bytes(), self.body)
            self.assertFalse(list(Path(folder).glob('*.part')))

    def test_forged_download_metadata_is_rejected_before_network(self):
        release = updater.validate_release(self.payload(), self.repository)
        release['url'] = 'https://evil.example/app.exe'
        opener = Mock()
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            updater.download_release(release, folder, opener)
        opener.open.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows replacement helper')
    def test_windows_helper_replaces_only_target_and_preserves_backup_and_settings(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build') as folder:
            root = Path(folder)
            staged = root / 'update.exe'
            staged.write_bytes((Path(os.environ['SystemRoot']) / 'System32/whoami.exe').read_bytes())
            target = root / 'app.exe'
            target.write_bytes(b'MZ old version sentinel')
            config = root / 'config.json'
            config.write_text('{"sender_id":"custom"}')
            digest = hashlib.sha256(staged.read_bytes()).hexdigest()
            script = updater.replacement_script(staged, target, digest, 0) + ' -Wait'
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                                     base64.b64encode(script.encode('utf-16le')).decode('ascii')],
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual(target.read_bytes(), staged.read_bytes())
            self.assertEqual((root / 'app.exe.bak').read_bytes(), b'MZ old version sentinel')
            self.assertEqual(json.loads(config.read_text()), {'sender_id': 'custom'})

    @unittest.skipUnless(os.name == 'nt', 'Windows replacement helper')
    def test_windows_helper_hash_failure_leaves_original_untouched(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build') as folder:
            root = Path(folder)
            staged, target = root / 'staged.exe', root / 'app.exe'
            staged.write_bytes(self.body)
            target.write_bytes(b'original')
            script = updater.replacement_script(staged, target, '0'*64, 0)
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                                     base64.b64encode(script.encode('utf-16le')).decode('ascii')], capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b'original')
            self.assertFalse((root / 'app.exe.new').exists())
