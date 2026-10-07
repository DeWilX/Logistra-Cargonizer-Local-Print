import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import logistra
import printer_setup as printer
import friendly_gui as gui


class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.body = b'%PDF-1.4\noriginal content\n%%EOF'
        self.source = self.root / 'data/reprint-123_ORD-12345678901.pdf'
        self.source.write_bytes(self.body)
        self.cfg = {'printer': 'Microsoft Print to PDF'}

    def test_cached_export_preserves_bytes_without_api_or_print(self):
        destination = self.root / 'saved.pdf'
        destination.write_bytes(b'old')
        with patch.object(printer, 'ROOT', self.root), patch.object(printer, 'Client') as client, patch.object(printer, 'print_pdf') as printing:
            printer.export_label(self.cfg, '123', destination)
        self.assertEqual(destination.read_bytes(), self.body)
        self.assertEqual(self.source.read_bytes(), self.body)
        self.assertEqual(list(self.root.glob('.logistra-*')), [])
        client.assert_not_called()
        printing.assert_not_called()

    def test_new_export_downloads_original_without_print(self):
        destination = self.root / 'saved.pdf'
        with patch.object(printer, 'ROOT', self.root), patch.object(printer, 'Client') as client, patch.object(printer, 'print_pdf') as printing:
            client.return_value.pdf.return_value = self.body
            printer.export_label(self.cfg, '456', destination)
        self.assertEqual(destination.read_bytes(), self.body)
        client.return_value.pdf.assert_called_once_with('456')
        printing.assert_not_called()

    def test_export_to_source_keeps_original(self):
        printer.save_pdf_copy(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), self.body)

    def test_save_dialog_starts_in_app_pdf_folder_not_documents(self):
        with patch.object(printer, 'ROOT', self.root), patch.object(printer.filedialog, 'asksaveasfilename', return_value='') as dialog:
            self.assertEqual(printer.choose_pdf_destination(None, '123_ORD-456.pdf'), '')
        self.assertEqual(dialog.call_args.kwargs['initialdir'], str(self.root / 'data'))
        self.assertEqual(dialog.call_args.kwargs['initialfile'], '123_ORD-456.pdf')

    def test_cancelled_save_does_not_export_or_print(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.identifier = Mock()
        app.identifier.get.return_value = '123'
        app.root = Mock()
        app.task = Mock(side_effect=lambda action, completed: completed(action()))
        with patch.object(gui, 'read_config', return_value=self.cfg), patch.object(gui, 'label_file', return_value=self.source), patch.object(gui, 'choose_pdf_destination', return_value='') as destination, patch.object(gui.messagebox, 'askyesno') as confirmation, patch.object(gui, 'save_pdf_copy') as export:
            app.quick_reprint()
        destination.assert_called_once_with(app.root, '123_ORD-12345678901.pdf')
        export.assert_not_called()
        confirmation.assert_not_called()

    def test_virtual_auto_print_refused_before_job_or_download(self):
        with patch.object(logistra, 'ROOT', self.root):
            db = logistra.database()
            self.addCleanup(db.close)
            client = Mock()
            with self.assertRaises(RuntimeError):
                logistra.process(db, client, self.cfg, '123', True)
            self.assertIsNone(db.execute('SELECT * FROM jobs').fetchone())
            client.pdf.assert_not_called()

    def test_export_does_not_confirm_physical_printer(self):
        cfg = {**self.cfg, 'printer_tested': True, 'tested_print_setup': ['Microsoft Print to PDF', 'adobe', 'reader']}
        with patch.object(gui.engine, 'pdf_executable', return_value='reader'):
            self.assertFalse(gui.print_setup_matches(cfg))
        window = printer.PrinterWindow.__new__(printer.PrinterWindow)
        window.history = {}
        window.message = Mock()
        window.on_print = Mock()
        with patch.object(printer, 'saved_labels', return_value=['123']):
            window.export_completed(None)
        window.on_print.assert_not_called()


if __name__ == '__main__':
    unittest.main()
