import queue
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import shipment_browser as browser
import friendly_gui as gui
import logistra_gui


class MultiSelectionTests(unittest.TestCase):
    def test_toolbar_action_receives_all_selected_shipments(self):
        view = browser.ShipmentBrowser.__new__(browser.ShipmentBrowser)
        view.table = Mock()
        view.table.selection.return_value = ('123', '456', '789')
        view.app = Mock()
        callback = Mock()
        view.selected_action(callback)
        callback.assert_called_once_with(identifiers=['123', '456', '789'])
        view.table.selection_set.assert_not_called()

    def test_ctrl_shift_click_only_selects_and_does_not_print(self):
        view = browser.ShipmentBrowser.__new__(browser.ShipmentBrowser)
        view.table = Mock()
        view.app = Mock()
        view.app.task_busy = False
        for modifier in (1, 4, 5):
            view.row_action(SimpleNamespace(state=modifier, x=20, y=30))
        view.table.selection_set.assert_not_called()
        view.app.download.assert_not_called()
        view.app.quick_reprint.assert_not_called()

    def test_bulk_download_uses_each_selected_id(self):
        app = logistra_gui.App.__new__(logistra_gui.App)
        app.task = lambda action, completed: completed(action())
        app.log = Mock()
        with patch.object(logistra_gui, 'read_config', return_value={}), patch.object(logistra_gui.engine, 'Client'), patch.object(logistra_gui.engine, 'download_label', return_value=Path('label.pdf')) as download:
            app.download(identifiers=['123', '456'])
        self.assertEqual([call.args[1] for call in download.call_args_list], ['123', '456'])

    def test_physical_batch_stops_on_uncertain_result_without_retry(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.root = Mock()
        app.events = queue.Queue()
        app.log = Mock()
        app.task = lambda action, completed: completed(action())
        with patch.object(gui, 'read_config', return_value={'printer': 'TSC'}), patch.object(gui.messagebox, 'askyesno', return_value=True), patch.object(gui, 'reprint_label', side_effect=[None, TimeoutError('unknown')]) as printing:
            with self.assertRaisesRegex(RuntimeError, '456'):
                app.reprint_multiple(['123', '456', '789'])
        self.assertEqual([call.args[1] for call in printing.call_args_list], ['123', '456'])

    def test_cancelled_virtual_batch_does_not_export_or_print(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.root = Mock()
        app.task = lambda action, completed: completed(action())
        cfg = {'printer': 'Microsoft Print to PDF'}
        with patch.object(gui, 'read_config', return_value=cfg), patch.object(gui, 'label_file', side_effect=[Path('123_ORD-123.pdf'), Path('456_ORD-456.pdf')]), patch.object(gui.filedialog, 'askdirectory', return_value=''), patch.object(gui, 'save_pdf_copy') as export, patch.object(gui, 'reprint_label') as printing:
            app.reprint_multiple(['123', '456'])
        export.assert_not_called()
        printing.assert_not_called()


if __name__ == '__main__':
    unittest.main()
