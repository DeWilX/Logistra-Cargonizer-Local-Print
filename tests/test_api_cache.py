import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import logistra
import friendly_gui


class ApiCacheTests(unittest.TestCase):
    def setUp(self):
        logistra._api_cache.clear()
        self.addCleanup(logistra._api_cache.clear)
        self.clock = patch.object(logistra.time, 'monotonic', return_value=100)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.cooldown = patch.object(logistra.Client, 'retry_not_before', 0)
        self.cooldown.start()
        self.addCleanup(self.cooldown.stop)

    def client(self, sender='12345', key='synthetic-key'):
        client = logistra.Client.__new__(logistra.Client)
        client.cfg = {'sender_id': sender, 'list_path': '/consignments.xml', 'list_verified': True}
        client.key = key
        client.pagination = {}
        client.references = {}
        client.opener = Mock()
        def response(*args, **kwargs):
            stream = io.BytesIO(b'<consignments/>')
            stream.headers = {'X-Pagination-Total-Pages': '1', 'X-Pagination-Total-Count': '0'}
            return stream
        client.opener.open.side_effect = response
        return client

    def test_list_cache_expires_and_retains_pagination(self):
        first, second = self.client(), self.client()
        first.get('/consignments.xml')
        second.get('/consignments.xml')
        second.opener.open.assert_not_called()
        self.assertEqual(second.pagination, first.pagination)
        self.now.return_value = 102.1
        second.get('/consignments.xml')
        second.opener.open.assert_called_once()

    def test_account_and_key_isolation_and_manual_refresh(self):
        first = self.client()
        first.get('/consignments/123.xml')
        for client in [self.client(sender='54321'), self.client(key='another-synthetic-key')]:
            client.get('/consignments/123.xml')
            client.opener.open.assert_called_once()
        first.get('/consignments/123.xml', fresh=True)
        self.assertEqual(first.opener.open.call_count, 2)
        self.now.return_value = 131
        first.get('/consignments/123.xml')
        self.assertEqual(first.opener.open.call_count, 3)

    def test_automatic_discovery_and_pdf_always_use_fresh_requests(self):
        client = self.client()
        client.ids()
        client.ids()
        client.get('/consignments/label_pdf?consignment_ids%5B%5D=123')
        client.get('/consignments/label_pdf?consignment_ids%5B%5D=123')
        self.assertEqual(client.opener.open.call_count, 4)

    def test_cache_size_is_bounded_and_errors_are_not_cached(self):
        client = self.client()
        for identifier in range(1, 131):
            client.get(f'/consignments/{identifier}.xml')
        self.assertEqual(len(logistra._api_cache), 128)
        client.opener.open.side_effect = RuntimeError('network unavailable')
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                client.get('/consignments/999.xml')
        self.assertFalse(any(key[2].endswith('/999.xml') for key in logistra._api_cache))

    def test_successful_empty_history_is_green_without_enabling_auto_print(self):
        app = friendly_gui.FriendlyApp.__new__(friendly_gui.FriendlyApp)
        for name in ('interval_status', 'status', 'summary', 'progress', 'root'):
            setattr(app, name, Mock())
        app.worker = None
        app.printer_ui = Mock(names=[])
        app.shipments_browser = SimpleNamespace(load_succeeded=True)
        app.status_dots = [Mock(), Mock(), Mock()]
        app.setup_state = ((False, False, False), False)
        cfg = {'poll_seconds': 15, 'printer': '', 'sender_id': '', 'list_verified': False}
        with patch.object(friendly_gui, 'read_config', return_value=cfg):
            app.update_dashboard()
        app.status_dots[2].configure.assert_called_with(foreground='#16a34a')
        self.assertFalse(cfg['list_verified'])
