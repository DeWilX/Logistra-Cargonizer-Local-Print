import unittest
from unittest.mock import Mock, patch

import friendly_gui as gui


class GuidedSetupTests(unittest.TestCase):
    def test_automatic_printing_can_start_without_test_print(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.task_busy = False
        app.worker = None
        app.printing = Mock(get=Mock(return_value=True))
        app.printer_ui = Mock(names=['Label printer'])
        app.tabs = Mock()
        app.log = Mock()
        app.task = lambda action, completed: completed(action())
        cfg = {'printer': 'Label printer', 'print_backend': 'adobe', 'api_verified': True,
               'list_verified': True, 'printer_tested': False}
        with patch.object(gui, 'read_config', return_value=cfg), patch.object(gui, 'write_config'), \
             patch.object(gui, 'prepare_baseline', return_value=0), \
             patch.object(gui.engine, 'pdf_executable', return_value='Reader.exe'), \
             patch.object(gui.Path, 'is_file', return_value=True), \
             patch.object(gui.App, 'start') as start:
            app.start()
        start.assert_called_once()
        app.tabs.select.assert_not_called()

    def test_status_green_only_when_start_accepts_it(self):
        self.assertEqual(gui.status_levels({}, False, True), ('partial', 'missing', 'partial'))
        self.assertEqual(gui.status_levels({}, False, None), ('missing', 'missing', 'missing'))
        ready = {'api_verified': True, 'list_verified': True}
        self.assertEqual(gui.status_levels(ready, True, True), ('ok', 'ok', 'ok'))
        self.assertEqual(gui.status_levels(ready, True, False), ('ok', 'ok', 'partial'))

    def run_buttons_app(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.start_button, app.skip_button, app.stop_button = Mock(), Mock(), Mock()
        app.interval_label = Mock()
        app.run_buttons_state = None
        app.stop = Mock(is_set=Mock(return_value=False))
        return app

    def test_only_stop_is_shown_while_running(self):
        app = self.run_buttons_app()
        app.update_run_buttons(True)
        app.stop_button.pack.assert_called_once()
        app.start_button.pack.assert_not_called()
        app.skip_button.pack.assert_not_called()
        app.update_run_buttons(False)
        app.start_button.pack.assert_called_once()
        app.skip_button.pack.assert_called_once()
        app.stop_button.pack.assert_called_once()

    def skip_app(self, answer):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.task_busy = False
        app.worker = None
        app.root = Mock()
        app.verified = Mock()
        app.setup_card = Mock()
        app.log = Mock()
        app.start = Mock()
        return app

    def test_skip_checks_marks_setup_done_and_starts(self):
        app = self.skip_app(True)
        with patch.object(gui.messagebox, 'askyesno', return_value=True), patch.object(gui, 'write_config') as write:
            app.skip_checks_and_start()
        values = write.call_args.args[0]
        self.assertTrue(values['api_verified'] and values['list_verified'] and values['setup_dismissed'])
        app.start.assert_called_once()

    def test_skip_checks_cancel_changes_nothing(self):
        app = self.skip_app(False)
        with patch.object(gui.messagebox, 'askyesno', return_value=False), patch.object(gui, 'write_config') as write:
            app.skip_checks_and_start()
        write.assert_not_called()
        app.start.assert_not_called()

    def test_dashboard_uses_saved_interval_and_refreshes_after_change(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.worker = None
        app.interval_status = Mock()
        app.status = Mock()
        app.summary = Mock()
        app.progress = Mock()
        app.root = Mock()
        app.setup_state = ((False, False, False), False)
        app.status_dots = [Mock(), Mock(), Mock()]
        app.printer_ui = Mock(names=[])
        cfg = {'sender_id': '12345', 'poll_seconds': 60, 'printer': 'TSC DA210', 'printer_tested': True}
        with patch.object(gui, 'read_config', return_value=cfg):
            app.update_dashboard()
            app.interval_status.set.assert_called_with('Pārbaude ik pēc 60 sekundēm')
            self.assertIn('Printeris: nav iestatīts', app.summary.set.call_args.args[0])
            app.status_dots[1].configure.assert_called_with(foreground='#ef4444')
            cfg['poll_seconds'] = 30
            app.update_dashboard()
            app.interval_status.set.assert_called_with('Pārbaude ik pēc 30 sekundēm')

    def test_manual_confirmation_does_not_print_or_call_api(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.worker = None
        app.snapshot = Mock(return_value={'sender_id':'12345','autostart':False})
        app.key = Mock()
        app.key.get.return_value = ''
        app.printer_ui = Mock()
        app.printer_ui.names = ['TSC']
        app.printer_ui.printer.get.return_value = 'TSC'
        app.printer_ui.backend.get.return_value = 'cups'
        app.printer_ui.executable.get.return_value = ''
        app.verified = Mock()
        app.tabs = Mock()
        app.home = Mock()
        app.log = Mock()
        app.setup_card = Mock()
        app.task = lambda action, completed: completed(action())
        cfg = {'printer':'TSC','print_backend':'cups'}
        with patch.object(gui, 'save_printer', return_value=cfg), \
             patch.object(gui, 'configure_startup'), patch.object(gui, 'write_config') as write, \
             patch.object(gui.engine, 'api_key', return_value='test'), \
             patch.object(gui.engine, 'pdf_executable', return_value='/usr/bin/lp'), \
             patch.object(gui.engine, 'Client') as client, patch.object(gui.engine, 'print_pdf') as printer:
            app.manual_confirm()
        client.assert_not_called()
        printer.assert_not_called()
        values = write.call_args.args[0]
        self.assertEqual(values, {'setup_dismissed': True})
        app.setup_card.pack_forget.assert_called_once()

    def test_new_shipment_must_be_in_list_open_and_have_pdf(self):
        client = Mock()
        client.ids.return_value = ['123']
        client.get.return_value = b'<consignments><consignment><id>123</id><state>open</state></consignment></consignments>'
        with patch.object(gui.engine, 'Client', return_value=client):
            self.assertEqual(gui.verify_open_shipment({}, '123'), '123')
        client.pdf.assert_called_once_with('123')

    def test_transferred_shipment_is_valid_for_automation_verification(self):
        client = Mock()
        client.ids.return_value = ['123']
        client.get.return_value = b'<consignments><consignment><id>123</id><state>transferred</state></consignment></consignments>'
        with patch.object(gui.engine, 'Client', return_value=client):
            self.assertEqual(gui.verify_open_shipment({}, '123'), '123')
        client.pdf.assert_called_once_with('123')

    def test_missing_shipment_does_not_enable_automation(self):
        client = Mock()
        client.ids.return_value = []
        with patch.object(gui.engine, 'Client', return_value=client):
            with self.assertRaises(ValueError):
                gui.verify_open_shipment({}, '123')

    def test_test_print_is_optional_but_printing_program_is_required(self):
        cfg = {'printer':'TSC', 'print_backend':'cups', 'printer_tested': True,
               'tested_print_setup':['TSC','cups','/usr/bin/lp']}
        with patch.object(gui.engine, 'pdf_executable', return_value='/usr/bin/lp'), patch.object(gui.Path, 'is_file', return_value=True):
            self.assertTrue(gui.print_setup_matches(cfg))
            cfg['printer']='Other'
            cfg['printer_tested'] = False
            self.assertTrue(gui.print_setup_matches(cfg))
        with patch.object(gui.Path, 'is_file', return_value=False):
            self.assertFalse(gui.print_setup_matches(cfg))
