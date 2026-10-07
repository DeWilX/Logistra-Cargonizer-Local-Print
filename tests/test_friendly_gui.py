import unittest
from unittest.mock import Mock, patch

import friendly_gui as gui


class GuidedSetupTests(unittest.TestCase):
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

    def test_transferred_shipment_does_not_enable_automation(self):
        client = Mock()
        client.ids.return_value = ['123']
        client.get.return_value = b'<consignments><consignment><id>123</id><state>transferred</state></consignment></consignments>'
        with patch.object(gui.engine, 'Client', return_value=client):
            with self.assertRaises(ValueError):
                gui.verify_open_shipment({}, '123')
        client.pdf.assert_not_called()

    def test_missing_shipment_does_not_enable_automation(self):
        client = Mock()
        client.ids.return_value = []
        with patch.object(gui.engine, 'Client', return_value=client):
            with self.assertRaises(ValueError):
                gui.verify_open_shipment({}, '123')

    def test_changed_printer_requires_a_new_test(self):
        cfg = {'printer':'TSC', 'print_backend':'cups', 'printer_tested': True,
               'tested_print_setup':['TSC','cups','/usr/bin/lp']}
        with patch.object(gui.engine, 'pdf_executable', return_value='/usr/bin/lp'):
            self.assertTrue(gui.print_setup_matches(cfg))
            cfg['printer']='Other'
            self.assertFalse(gui.print_setup_matches(cfg))
