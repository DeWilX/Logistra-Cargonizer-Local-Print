from datetime import date
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import shipment_browser as browser


def xml(identifier, created):
    return f'<consignments><consignment id="{identifier}"><created-at>{created}</created-at><state>transferred</state></consignment></consignments>'.encode()


class HistoryTests(unittest.TestCase):
    def test_date_range_fetches_all_pages_and_reports_progress(self):
        client = Mock()
        client.pagination = {'Total-Pages': '2', 'Total-Count': '2'}
        client.get.side_effect = [xml('123', '2026-10-02T12:00:00Z'), xml('456', '2020-09-02T12:00:00Z')]
        progress = Mock()
        with patch.object(browser, 'Client', return_value=client):
            rows = browser.load_shipments({}, 'Visi', date(2020, 9, 1), date(2026, 10, 7), progress)
        self.assertEqual([row['id'] for row in rows], ['123', '456'])
        queries = [parse_qs(urlsplit(call.args[0]).query) for call in client.get.call_args_list]
        self.assertEqual([query['page'] for query in queries], [['1'], ['2']])
        for query in queries:
            self.assertEqual(query['from'], ['2020-09-01'])
            self.assertEqual(query['to'], ['2026-10-07'])
            self.assertEqual(query['state[]'], ['all'])
        self.assertEqual(progress.call_count, 2)

    def test_repeated_page_is_rejected_instead_of_presented_as_full_history(self):
        client = Mock()
        client.pagination = {'Total-Pages': '2', 'Total-Count': '2'}
        client.get.return_value = xml('123', '2026-10-02T12:00:00Z')
        with patch.object(browser, 'Client', return_value=client), self.assertRaisesRegex(ValueError, 'atkārto'):
            browser.load_shipments({})

    def test_incomplete_total_and_missing_headers_are_rejected(self):
        client = Mock()
        client.get.return_value = xml('123', '2026-10-02T12:00:00Z')
        for headers in [{'Total-Pages': '1', 'Total-Count': '2'}, {}]:
            client.pagination = headers
            with patch.object(browser, 'Client', return_value=client), self.assertRaises(ValueError):
                browser.load_shipments({})

    def test_empty_historical_period_is_normal(self):
        client = Mock()
        client.pagination = {'Total-Pages': '0', 'Total-Count': '0'}
        client.get.return_value = b'<consignments/>'
        with patch.object(browser, 'Client', return_value=client):
            self.assertEqual(browser.load_shipments({}), [])

    def test_filter_button_fetches_changed_period_and_filters_existing_period_locally(self):
        view = browser.ShipmentBrowser.__new__(browser.ShipmentBrowser)
        view.start_date = Mock()
        view.end_date = Mock()
        view.start_date.get.return_value = '01.09.2020'
        view.end_date.get.return_value = '07.10.2026'
        view.loaded_period = (date(2026, 9, 1), date(2026, 10, 7))
        view.load = Mock()
        view.render = Mock()
        view.apply_filters()
        view.load.assert_called_once()
        view.loaded_period = (date(2020, 9, 1), date(2026, 10, 7))
        view.apply_filters()
        view.render.assert_called_once()
