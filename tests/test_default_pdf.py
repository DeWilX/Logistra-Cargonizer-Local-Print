import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import printer_setup as printer


class DefaultPdfTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.destination = self.root / 'chosen PDFs'
        self.cfg = {'printer': 'TSC', 'pdf_directory': str(self.destination)}
        (self.root / 'config.json').write_text(json.dumps(self.cfg), encoding='utf-8')

    def window(self, name='TSC'):
        window = printer.PrinterWindow.__new__(printer.PrinterWindow)
        window.printer = Mock()
        window.printer.get.return_value = name
        window.names = [name]
        window.backend = Mock()
        window.backend.get.return_value = 'adobe'
        window.executable = Mock()
        window.executable.get.return_value = 'reader.exe'
        window.message = Mock()
        window.window = Mock()
        window.background = Mock()
        return window

    def test_default_pdf_is_copied_to_selected_folder_without_api_or_history_change(self):
        history = self.root / 'data/state.sqlite'
        history.write_bytes(b'history sentinel')
        with patch.object(printer, 'ROOT', self.root), patch.object(printer, 'Client') as client:
            file = printer.default_test_pdf(self.cfg)
        self.assertEqual(file.parent, self.destination)
        self.assertEqual(file.read_bytes(), printer.asset('default-test-label.pdf').read_bytes())
        self.assertEqual(history.read_bytes(), b'history sentinel')
        client.assert_not_called()

    def test_print_button_uses_default_without_file_picker(self):
        window = self.window()
        with patch.object(printer, 'ROOT', self.root), patch.object(printer, 'print_pdf') as printing, patch.object(printer.filedialog, 'askopenfilename') as picker:
            window.print_selected()
            action = window.background.call_args.args[0]
            action()
        picker.assert_not_called()
        printing.assert_called_once()
        self.assertEqual(printing.call_args.args[1], self.destination / 'Logistra-testa-druka.pdf')

    def test_cancelled_virtual_default_test_does_not_print_or_create_file(self):
        window = self.window('Microsoft Print to PDF')
        with patch.object(printer, 'ROOT', self.root), patch.object(printer, 'choose_pdf_destination', return_value='') as destination, patch.object(printer, 'print_pdf') as printing:
            window.print_selected()
        destination.assert_called_once_with(window.window, 'Logistra-testa-druka.pdf')
        window.background.assert_not_called()
        printing.assert_not_called()
        self.assertFalse(self.destination.exists())
