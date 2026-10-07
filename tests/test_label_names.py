import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import logistra
import printer_setup


class LabelNameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.body = b'%PDF-1.4\noriginal\n%%EOF'

    def test_automatic_download_reference_name_and_restart_deduplication(self):
        client = Mock()
        client.pdf.return_value = self.body
        client.reference.return_value = 'ORD-12345678901'
        with patch.object(logistra, 'ROOT', self.root), patch.object(logistra, 'print_pdf') as printing:
            db = logistra.database()
            self.addCleanup(db.close)
            logistra.process(db, client, {}, '123')
            logistra.process(db, client, {}, '123', True)
            logistra.process(db, client, {}, '123', True)
            printing.assert_called_once_with({}, self.root / 'data/123_ORD-12345678901.pdf')
            client.pdf.assert_called_once()
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?', ('123',)).fetchone(), ('submitted',))
        self.assertEqual((self.root / 'data/123_ORD-12345678901.pdf').read_bytes(), self.body)

    def test_old_cached_pdf_gains_reference_without_redownload_or_history_change(self):
        source = self.root / 'data/reprint-123.pdf'
        source.write_bytes(self.body)
        history = self.root / 'data/state.sqlite'
        history.write_bytes(b'history sentinel')
        with patch.object(printer_setup, 'ROOT', self.root), patch.object(printer_setup, 'Client') as client:
            client.return_value.reference.return_value = 'ORD-12345678901'
            file = printer_setup.label_file({}, '123')
            self.assertEqual(file.name, 'reprint-123_ORD-12345678901.pdf')
            self.assertEqual(file.read_bytes(), self.body)
            self.assertEqual(printer_setup.saved_labels(), ['123'])
            client.return_value.pdf.assert_not_called()
        self.assertEqual(history.read_bytes(), b'history sentinel')

    def test_reference_from_list_and_detail_and_missing_reference(self):
        with patch.object(logistra, 'api_key', return_value='test'):
            client = logistra.Client({'sender_id': '12345', 'list_verified': True, 'list_path': '/consignments.xml'})
        with patch.object(client, 'get', return_value=b'<consignments><consignment id="123"><consignor-reference>ORD-12345678901</consignor-reference></consignment></consignments>') as get:
            self.assertEqual(client.ids(), ['123'])
            self.assertEqual(client.reference('123'), 'ORD-12345678901')
            get.assert_called_once()
        with patch.object(client, 'get', return_value=b'<consignment><consignor-reference>ORD-456</consignor-reference></consignment>') as get:
            self.assertEqual(client.reference('456'), 'ORD-456')
            get.assert_called_once_with('/consignments/456.xml')
        with patch.object(client, 'get', return_value=b'<consignments><consignment id="789"/></consignments>'):
            self.assertEqual(logistra.label_filename('789', client.reference('789')), '789.pdf')

    def test_reference_cannot_escape_pdf_folder(self):
        filename = logistra.label_filename('123', '../ORD-1/\\:*?"<>|\n')
        self.assertEqual(Path(filename).name, filename)
        self.assertNotIn('/', filename)
        self.assertNotIn('\\', filename)
        self.assertNotIn('\n', filename)
        self.assertEqual(logistra.label_identifier(filename), '123')


if __name__ == '__main__':
    unittest.main()
