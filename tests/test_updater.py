import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
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

    def page_response(self, body=b'', url='https://github.com/example/logistra/releases/tag/v1.2.0', headers=None):
        response = io.BytesIO(body)
        response.geturl = lambda: url
        response.headers = headers or {}
        return response

    def test_api_rate_limit_uses_official_release_page(self):
        error = updater.urllib.error.HTTPError('https://api.github.com', 403, 'rate limited', {'X-RateLimit-Remaining': '0'}, None)
        opener = Mock()
        opener.open.side_effect = error
        with patch.object(updater, 'github_opener', return_value=opener), patch.object(updater, 'check_release_page', return_value={'version': '1.2.0'}) as fallback:
            self.assertEqual(updater.check_release(self.repository, '1.0.0'), {'version': '1.2.0'})
            fallback.assert_called_once_with(self.repository, '1.0.0')

    def test_release_page_digest_and_size_pass_same_validation(self):
        asset = self.payload()['assets'][0]
        html = f'<li><a href="/example/logistra/releases/download/v1.2.0/Logistra-Print.exe">EXE</a><clipboard-copy aria-label="Copy to clipboard digest for Logistra-Print.exe" value="{asset["digest"]}"></clipboard-copy></li>'
        opener = Mock()
        opener.open.side_effect = [self.page_response(), self.page_response(html.encode()), self.page_response(headers={'Content-Length': str(len(self.body))})]
        self.assertEqual(updater.check_release_page(self.repository, '1.0.0', opener), updater.validate_release(self.payload(), self.repository, '1.0.0'))
        self.assertEqual(opener.open.call_args.args[0].get_method(), 'HEAD')

    def test_release_page_wrong_repository_and_missing_digest_are_rejected(self):
        opener = Mock()
        opener.open.return_value = self.page_response(url='https://github.com/other/repo/releases/tag/v1.2.0')
        with self.assertRaises(ValueError):
            updater.check_release_page(self.repository, '1.0.0', opener)
        html = '<li><a href="/example/logistra/releases/download/v1.2.0/Logistra-Print.exe">EXE</a></li>'
        opener.open.side_effect = [self.page_response(), self.page_response(html.encode())]
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            updater.check_release_page(self.repository, '1.0.0', opener)

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
    def test_failed_helper_start_keeps_application_open(self):
        with tempfile.TemporaryDirectory() as folder:
            staged, target = Path(folder) / 'staged.exe', Path(folder) / 'app.exe'
            staged.write_bytes(self.body)
            target.write_bytes(self.body)
            process = Mock()
            process.poll.return_value = 0
            with patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater.sys, 'executable', str(target)), patch.object(updater.subprocess, 'Popen', return_value=process):
                with self.assertRaisesRegex(RuntimeError, 'palīgprocess nesākās'):
                    updater.launch_replacement(staged, hashlib.sha256(self.body).hexdigest())
            self.assertEqual(target.read_bytes(), self.body)
            self.assertFalse(list(Path(folder).glob('update-ready-*')))

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
