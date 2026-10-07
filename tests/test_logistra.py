import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

import logistra


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.patch = patch.object(logistra, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db = logistra.database()
        self.addCleanup(self.db.close)
        self.client = Mock()
        self.client.pdf.return_value = b'%PDF-1.4\nmock'

    def state(self):
        return self.db.execute("SELECT status FROM jobs WHERE id='123'").fetchone()[0]

    def test_download_then_print_and_restart_deduplication(self):
        logistra.process(self.db, self.client, {}, '123')
        self.assertEqual(self.state(), 'downloaded')
        with patch.object(logistra, 'print_pdf') as printer:
            logistra.process(self.db, self.client, {}, '123', True)
            logistra.process(self.db, self.client, {}, '123', True)
            printer.assert_called_once()
        self.client.pdf.assert_called_once()
        self.assertEqual(self.state(), 'submitted')

    def test_failed_print_is_not_retried_automatically(self):
        with patch.object(logistra, 'print_pdf', side_effect=TimeoutError) as printer:
            with self.assertRaises(TimeoutError):
                logistra.process(self.db, self.client, {}, '123', True)
            logistra.process(self.db, self.client, {}, '123', True)
            printer.assert_called_once()
        self.assertEqual(self.state(), 'uncertain')

    def test_crash_after_submission_start_is_not_retried(self):
        logistra.status(self.db, '123', 'submitting')
        logistra.process(self.db, self.client, {}, '123', True)
        self.client.pdf.assert_not_called()

    def test_baseline_does_not_print(self):
        logistra.status(self.db, '123', 'baseline')
        logistra.process(self.db, self.client, {}, '123', True)
        self.client.pdf.assert_not_called()

    def test_download_failure_does_not_mark_job_complete(self):
        self.client.pdf.side_effect = RuntimeError('Label not ready')
        with self.assertRaises(RuntimeError):
            logistra.process(self.db, self.client, {}, '123')
        self.assertIsNone(self.db.execute('SELECT * FROM jobs').fetchone())
        self.client.pdf.side_effect = None
        logistra.process(self.db, self.client, {}, '123')
        self.assertEqual(self.state(), 'downloaded')

    def test_list_schema_and_invalid_ids(self):
        self.assertEqual(logistra.parse_ids(b'<consignments><consignment id="12"/><consignment><id>3</id></consignment></consignments>'), ['3', '12'])
        for body in [b'<html/>', b'<consignments><consignment/></consignments>']:
            with self.assertRaises(ValueError):
                logistra.parse_ids(body)
        for identifier in ['../x', '0', '-2', 'abc', '１２']:
            with self.assertRaises(ValueError):
                logistra.shipment_id(identifier)

    def test_discovery_disabled_until_verified(self):
        with patch.object(logistra, 'api_key', return_value='test'):
            client = logistra.Client({'sender_id': '12345', 'list_verified': False})
        with self.assertRaises(RuntimeError):
            client.ids()

    def test_html_is_not_saved_as_pdf(self):
        with patch.object(logistra, 'api_key', return_value='test'):
            client = logistra.Client({'sender_id': '12345'})
        with patch.object(client, 'get', return_value=b'<html>login</html>'):
            with self.assertRaises(RuntimeError):
                client.pdf('123')

    def test_incomplete_list_is_rejected(self):
        with patch.object(logistra, 'api_key', return_value='test'):
            client = logistra.Client({'sender_id': '12345', 'list_verified': True, 'list_path': '/consignments.xml'})
        for headers in [{'Total-Pages': '2', 'Total-Count': '101'},
                        {'Total-Pages': '1', 'Total-Count': '1'}]:
            client.pagination = headers
            with patch.object(client, 'get', return_value=b'<consignments/>'):
                with self.assertRaises(RuntimeError):
                    client.ids()
        client.pagination = {'Total-Pages': '0', 'Total-Count': '0'}
        with patch.object(client, 'get', return_value=b'<consignments/>'):
            self.assertEqual(client.ids(), [])

    def test_adobe_command_uses_printer_driver_and_port(self):
        file = self.root / 'label.pdf'
        executable = self.root / 'Acrobat.exe'
        executable.touch()
        details = Mock(returncode=0, stdout=b'{"Name":"Zebra","DriverName":"Zebra Driver","PortName":"USB001"}')
        result = Mock(returncode=0)
        with patch.object(logistra, 'os', SimpleNamespace(name='nt', environ={})), \
             patch.object(logistra.sys, 'platform', 'win32'), \
             patch.object(logistra, 'pdf_executable', return_value=executable), \
             patch.object(logistra.subprocess, 'run', side_effect=[details, result]) as run:
            logistra.print_pdf({'print_backend': 'adobe', 'printer': 'Zebra'}, file)
        self.assertEqual(run.call_args.args[0], [str(executable), '/t', str(file.resolve()), 'Zebra', 'Zebra Driver', 'USB001'])


if __name__ == '__main__':
    unittest.main()
