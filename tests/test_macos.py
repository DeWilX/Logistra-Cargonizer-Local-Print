import ctypes
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import Mock, patch

import logistra
import logistra_gui
import mac_support
import printer_setup


class MacTests(unittest.TestCase):
    def test_keychain_read_once_and_refresh_after_save(self):
        with patch.object(mac_support, '_cached_key', None), patch.object(mac_support, '_keychain_key', return_value='first') as access:
            self.assertEqual(mac_support.keychain_key(), 'first')
            self.assertEqual(mac_support.keychain_key(), 'first')
            access.assert_called_once_with(None)
            mac_support.keychain_key('second')
            self.assertEqual(mac_support.keychain_key(), 'second')
            self.assertEqual(access.call_count, 2)

    def test_tsc_queue_name_matching(self):
        self.assertEqual(printer_setup.preferred_printer(['Office', 'TSC_DA210'], 'TSC DA210'), 'TSC_DA210')
        self.assertEqual(printer_setup.preferred_printer(['TSC_DA210', 'TSC-DA210'], 'TSC DA210'), '')
    def test_printer_list(self):
        result = Mock(returncode=0, stdout='printer Zebra is idle.\nprinter Office is idle.\n', stderr='')
        with patch.object(printer_setup.sys, 'platform', 'darwin'), patch.object(printer_setup.subprocess, 'run', return_value=result):
            self.assertEqual(printer_setup.installed_printers(), ['Office', 'Zebra'])

    def test_no_installed_printers(self):
        result = Mock(returncode=1, stdout='', stderr='lpstat: No destinations added.')
        with patch.object(printer_setup.sys, 'platform', 'darwin'), patch.object(printer_setup.subprocess, 'run', return_value=result):
            self.assertEqual(printer_setup.installed_printers(), [])

    def test_cups_submission_one_copy_no_scaling(self):
        file = Path('/tmp/test-label.pdf')
        with patch.object(logistra.sys, 'platform', 'darwin'), patch.object(logistra.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            logistra.print_pdf({'printer': 'Zebra'}, file)
        self.assertEqual(run.call_args.args[0], ['/usr/bin/lp', '-d', 'Zebra', '-n', '1', '-o', 'sides=one-sided', '-o', 'print-scaling=none', str(file.resolve())])

    def test_cups_failure_is_reported(self):
        with patch.object(logistra.sys, 'platform', 'darwin'), patch.object(logistra.subprocess, 'run', return_value=Mock(returncode=1)):
            with self.assertRaises(RuntimeError):
                logistra.print_pdf({'printer': 'Zebra'}, Path('/tmp/label.pdf'))

    def test_keychain_storage_no_command_arguments(self):
        api = Mock()
        api.SecKeychainFindGenericPassword.return_value = -25300
        api.SecKeychainAddGenericPassword.return_value = 0
        with patch.object(mac_support, 'security_api', return_value=api), patch.object(mac_support.ctypes, 'CDLL', return_value=Mock()):
            mac_support.keychain_key('test-key')
        self.assertEqual(api.SecKeychainAddGenericPassword.call_args.args[6], b'test-key')

    def test_launchagent_created_and_removed(self):
        with tempfile.TemporaryDirectory() as d, patch.object(logistra_gui.sys, 'platform', 'darwin'), patch.object(logistra_gui.Path, 'home', return_value=Path(d)):
            logistra_gui.configure_startup(True)
            file = Path(d) / 'Library/LaunchAgents/app.logistra.print.plist'
            payload = plistlib.loads(file.read_bytes())
            self.assertTrue(payload['RunAtLoad'])
            self.assertEqual(payload['ProgramArguments'][-1], '--startup')
            logistra_gui.configure_startup(False)
            self.assertFalse(file.exists())


if __name__ == '__main__':
    unittest.main()
