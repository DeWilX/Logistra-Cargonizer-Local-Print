import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import logistra
import printer_setup as printer
import logistra_gui as gui


class PdfDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'application'
        (self.root / 'data').mkdir(parents=True)
        self.destination = Path(self.temp.name) / 'chosen PDFs'
        self.cfg = {'pdf_directory': str(self.destination)}
        (self.root / 'config.json').write_text(json.dumps(self.cfg), encoding='utf-8')
        self.body = b'%PDF-1.4\noriginal content\n%%EOF'

    def test_custom_download_and_reprint_use_same_folder_with_history_in_app_data(self):
        client = Mock()
        client.cfg = self.cfg
        client.pdf.return_value = self.body
        client.reference.return_value = 'ORD-123'
        with patch.object(logistra, 'ROOT', self.root), patch.object(printer, 'ROOT', self.root), patch.object(printer, 'Client') as manual_client:
            db = logistra.database()
            self.addCleanup(db.close)
            logistra.process(db, client, self.cfg, '123')
            file = printer.label_file(self.cfg, '123')
            self.assertEqual(file, self.destination / '123_ORD-123.pdf')
            self.assertEqual(file.read_bytes(), self.body)
            self.assertEqual(printer.saved_labels(), ['123'])
            manual_client.assert_not_called()
        self.assertTrue((self.root / 'data/state.sqlite').is_file())
        self.assertFalse((self.destination / 'state.sqlite').exists())

    def test_folder_change_copies_pdfs_and_preserves_originals_and_history(self):
        source = self.root / 'data/reprint-123_ORD-123.pdf'
        source.write_bytes(self.body)
        history = self.root / 'data/state.sqlite'
        history.write_bytes(b'history sentinel')
        with patch.object(printer, 'ROOT', self.root):
            self.assertEqual(printer.prepare_pdf_directory({}, self.destination), str(self.destination))
        self.assertEqual(source.read_bytes(), self.body)
        self.assertEqual((self.destination / source.name).read_bytes(), self.body)
        self.assertEqual(history.read_bytes(), b'history sentinel')
        self.assertFalse((self.destination / history.name).exists())

    def test_different_existing_pdf_is_not_overwritten_on_folder_change(self):
        source = self.root / 'data/123.pdf'
        source.write_bytes(self.body)
        self.destination.mkdir()
        target = self.destination / source.name
        target.write_bytes(b'%PDF-1.4\ndifferent content')
        with patch.object(printer, 'ROOT', self.root), self.assertRaises(ValueError):
            printer.prepare_pdf_directory({}, self.destination)
        self.assertEqual(target.read_bytes(), b'%PDF-1.4\ndifferent content')
        self.assertEqual(source.read_bytes(), self.body)

    def test_dialog_and_open_pdf_folder_use_saved_directory(self):
        with patch.object(printer, 'ROOT', self.root), patch.object(printer.filedialog, 'asksaveasfilename', return_value='') as dialog:
            printer.choose_pdf_destination(None, '123_ORD-123.pdf')
            self.assertEqual(dialog.call_args.kwargs['initialdir'], str(self.destination))
        if gui.os.name == 'nt':
            app = gui.App.__new__(gui.App)
            with patch.object(gui, 'read_config', return_value=self.cfg), patch.object(gui.os, 'startfile') as open_folder:
                app.open_folder()
                open_folder.assert_called_once_with(self.destination)


if __name__ == '__main__':
    unittest.main()
