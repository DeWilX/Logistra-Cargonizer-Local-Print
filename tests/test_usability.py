from datetime import date
import io
import unittest
from unittest.mock import Mock, patch
import urllib.error

import friendly_gui as gui
import logistra
from logistra_gui import App
from shipment_browser import preset_period
from date_picker import shift_month
from reference_search import find_reference


class UsabilityTests(unittest.TestCase):
    def test_presets_cross_year_and_leap_month(self):
        self.assertEqual(preset_period('Pagājušajā mēnesī', date(2024, 3, 1)), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(preset_period('Pagājušajā nedēļā', date(2026, 1, 1)), (date(2025, 12, 22), date(2025, 12, 28)))
        start, end = preset_period('Pēdējās 30 dienas', date(2026, 10, 7))
        self.assertEqual((end-start).days, 29)
        self.assertEqual(shift_month(2026, 1, -1), (2025, 12))

    def test_order_lookup_is_exact_and_returns_all_matches(self):
        rows = [{'id': '1', 'reference': 'ORD-123'}, {'id': '2', 'reference': ' ord-123 '}, {'id': '3', 'reference': 'ORD-1234'}]
        with patch('reference_search.load_shipments', return_value=rows) as load:
            self.assertEqual([row['id'] for row in find_reference({}, 'ORD-123')], ['1', '2'])
            load.assert_called_once_with({}, 'Visi', start=date(1900, 1, 1), end=date.today(), progress=None)

    def test_open_loads_only_with_key_and_retries_busy_ui(self):
        app = gui.FriendlyApp.__new__(gui.FriendlyApp)
        app.closing = False
        app.task_busy = False
        app.shipments_browser = Mock()
        app.root = Mock()
        with patch.object(gui.engine, 'api_key', return_value='test'), patch.object(gui.sys, 'argv', ['app.exe']):
            app.load_on_open()
            app.shipments_browser.load.assert_called_once()
            app.task_busy = True
            app.load_on_open()
            app.root.after.assert_called_once_with(500, app.load_on_open)
        app.task_busy = False
        app.shipments_browser.reset_mock()
        with patch.object(gui.engine, 'api_key', side_effect=RuntimeError('No key')):
            app.load_on_open()
        app.shipments_browser.load.assert_not_called()

    def test_minimum_interval_is_five_seconds(self):
        app = App.__new__(App)
        for name, value in [('sender', '12345'), ('path', '/consignments.xml'), ('interval', '1'), ('verified', True), ('printing', False), ('autostart', False)]:
            setattr(app, name, Mock(get=Mock(return_value=value)))
        self.assertEqual(app.snapshot()['poll_seconds'], 5)

    def test_rate_limit_pauses_new_clients_without_retrying_request(self):
        client = logistra.Client.__new__(logistra.Client)
        client.key = 'test'
        client.cfg = {'sender_id': '12345'}
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError('https://api.cargonizer.no', 429, 'limit', {'Retry-After': '30'}, io.BytesIO())
        with patch.object(logistra.Client, 'retry_not_before', 0), patch.object(logistra.time, 'monotonic', return_value=100):
            with self.assertRaisesRegex(RuntimeError, '30 sekundes'):
                client.get('/consignments.xml')
            with self.assertRaisesRegex(RuntimeError, 'nākamais mēģinājums'):
                client.get('/consignments.xml')
            client.opener.open.assert_called_once()
