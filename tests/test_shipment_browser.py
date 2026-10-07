from datetime import date
import unittest
from unittest.mock import Mock, patch

import shipment_browser as browser

XML = b'''<consignments><consignment><id>123</id><state>transferred</state>
<created-at>2026-10-02T08:21:44Z</created-at><consignor-reference>ORDER-1</consignor-reference>
<transport-agreement><carrier><name>PostNord</name></carrier></transport-agreement>
<product><name>Service Point</name></product><number>123456</number>
<bundles><bundle><pieces><piece/><piece/></pieces></bundle></bundles>
<addresses><address type="ConsigneeAddress"><name>Example Customer</name><country>NO</country><postcode>1480</postcode><city>Slattum</city></address></addresses>
</consignment></consignments>'''


class BrowserTests(unittest.TestCase):
    def test_columns_fill_available_width_and_preserve_minimums(self):
        minimums={'#0':118,'recipient':170,'address':160,'carrier':100,'product':120,'reference':160,'items':55,'date':100,'number':185,'status':95}
        widths=browser.fit_column_widths(1500,minimums)
        self.assertEqual(sum(widths.values()),1500)
        self.assertEqual(widths['#0'],118)
        self.assertTrue(all(widths[name]>=width for name,width in minimums.items()))
        self.assertEqual(browser.fit_column_widths(800,minimums),minimums)
    def test_response_fields_and_search(self):
        rows = browser.parse_shipments(XML)
        self.assertEqual(rows[0]['carrier'], 'PostNord')
        self.assertEqual(rows[0]['recipient'], 'Example Customer')
        self.assertEqual(rows[0]['address'], 'NO-1480 Slattum')
        self.assertEqual(rows[0]['product'], 'Service Point')
        self.assertEqual(rows[0]['items'], 2)
        self.assertEqual(rows[0]['number'], '123456')
        self.assertEqual(len(browser.filter_shipments(rows, search='order-1')), 1)
        self.assertEqual(browser.filter_shipments(rows, carrier='Other'), [])
        self.assertEqual(len(browser.filter_shipments(rows, start=date(2026,10,1), end=date(2026,10,3))), 1)
        self.assertEqual(browser.filter_shipments(rows, start=date(2026,10,7)), [])

    def test_all_requests_all_states(self):
        client = Mock()
        client.pagination = {'Total-Pages':'1', 'Total-Count':'1'}
        client.get.return_value = XML
        with patch.object(browser, 'Client', return_value=client):
            self.assertEqual(len(browser.load_shipments({}, 'Visi')), 1)
        self.assertEqual([call.args[0] for call in client.get.call_args_list], ['/consignments.xml?page=1&per_page=100&state%5B%5D=all'])

    def test_sent_view_and_multipage_rejection(self):
        client = Mock()
        client.pagination = {'Total-Pages':'2', 'Total-Count':'101'}
        client.get.return_value = XML
        with patch.object(browser, 'Client', return_value=client):
            with self.assertRaises(ValueError):
                browser.load_shipments({}, 'Nosūtītie')
        self.assertEqual(client.get.call_count, 2)

    def test_invalid_date_range(self):
        with self.assertRaises(ValueError):
            browser.filter_shipments([], start=date(2026,10,7), end=date(2026,10,1))
