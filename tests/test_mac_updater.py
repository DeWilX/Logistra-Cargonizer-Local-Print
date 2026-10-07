import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo
import mac_updater
import updater


class MacUpdateTests(unittest.TestCase):
    def archive(self, directory, extra=None):
        path = Path(directory) / 'Logistra-macOS-arm64-1.2.0.zip'
        with ZipFile(path, 'w') as archive:
            archive.writestr('Logistra.app/Contents/MacOS/Logistra', b'\xcf\xfa\xed\xfefixture')
            archive.writestr('Logistra.app/Contents/Resources/release-info.json', json.dumps({'version': '1.2.0'}))
            if extra:
                archive.writestr(*extra)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_verified_bundle_and_hash_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path, digest = self.archive(folder)
            self.assertEqual(mac_updater.validate_archive(path, digest), path.resolve())
            with self.assertRaises(ValueError):
                mac_updater.validate_archive(path, '0' * 64)

    def test_traversal_and_escaping_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('../outside', '/outside', 'Logistra.app/../outside'):
                path, digest = self.archive(folder, (name, 'bad'))
                with self.assertRaises(ValueError):
                    mac_updater.validate_archive(path, digest)
            info = ZipInfo('Logistra.app/Contents/Resources/link')
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            path, digest = self.archive(folder, (info, '../../../../outside'))
            with self.assertRaises(ValueError):
                mac_updater.validate_archive(path, digest)

    def test_mac_asset_and_official_release_validation(self):
        with patch.object(updater.sys, 'platform', 'darwin'), patch.object(updater.platform, 'machine', return_value='arm64'):
            self.assertEqual(updater.platform_asset(), 'Logistra-macOS-arm64.zip')
        name = 'Logistra-macOS-arm64.zip'
        payload = {'tag_name': 'v1.2.0', 'assets': [{'name': name, 'state': 'uploaded', 'size': 100,
                   'digest': 'sha256:' + 'a' * 64, 'browser_download_url': 'https://github.com/example/app/releases/download/v1.2.0/' + name}]}
        self.assertTrue(updater.validate_release(payload, 'example/app', '1.0.0', name))
        payload['assets'][0]['browser_download_url'] = 'https://evil.example/' + name
        with self.assertRaises(ValueError):
            updater.validate_release(payload, 'example/app', '1.0.0', name)

    def test_translocated_or_non_bundle_install_is_rejected(self):
        for path in ('/tmp/program', '/Volumes/Logistra.app/Contents/MacOS/Logistra', '/tmp/AppTranslocation/abc/Logistra.app/Contents/MacOS/Logistra'):
            with self.assertRaises(ValueError):
                mac_updater.installed_bundle(path)

    def test_helper_quotes_paths_and_keeps_backup_without_deleting_user_data(self):
        with tempfile.TemporaryDirectory(prefix="update ' space ") as folder:
            path, digest = self.archive(folder)
            target = Path(folder) / 'Logistra.app'
            target.mkdir()
            script = mac_updater.replacement_script(path, target, digest, 123)
            self.assertIn('PYINSTALLER_RESET_ENVIRONMENT=1', script)
            self.assertIn('kill -0 123', script)
            self.assertIn('update-backup-' + digest[:12], script)
            self.assertNotIn('rm ', script)
            self.assertIn('/usr/bin/open -n', script)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS helper syntax')
    def test_bash_and_administrator_applescript_compile(self):
        with tempfile.TemporaryDirectory(prefix="Logistra ' ü ") as folder:
            path, digest = self.archive(folder)
            target = Path(folder) / 'Logistra.app'
            target.mkdir()
            executable = target / 'Contents/MacOS/Logistra'
            with patch.object(mac_updater.sys, 'executable', str(executable)), patch.object(mac_updater.os, 'access', return_value=False), patch.object(mac_updater.subprocess, 'Popen'):
                mac_updater.launch_replacement(path, digest)
            for script in Path(folder).glob('*.sh'):
                subprocess.run(['/bin/bash', '-n', str(script)], check=True)
            subprocess.run(['/usr/bin/osacompile', '-o', str(Path(folder) / 'compiled.scpt'), str(Path(folder) / 'replace-macos.applescript')], check=True)
