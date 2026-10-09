"""Shipments that transfer faster than the polling interval must not be missed."""
from datetime import date, timedelta
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
import logistra


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        (Path(self.directory.name) / 'data').mkdir()
        self.root_patch = patch.object(logistra, 'ROOT', Path(self.directory.name))
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.db = logistra.database()
        self.addCleanup(self.db.close)
        self.client = Mock()
        self.client.cfg = {}
        self.client.reference.return_value = 'ORDER-TEST'
        self.client.pdf.return_value = b'%PDF-1.4\nsynthetic label'

    def test_shipment_seen_only_after_transfer_prints_once(self):
        self.client.ids.return_value = ['100']
        logistra.discovery_baseline(self.db, self.client)
        self.client.ids.return_value = ['100', '101']
        jobs = logistra.discover_jobs(self.db, self.client)
        self.assertEqual(jobs, ['101'])
        with patch.object(logistra, 'print_pdf') as printing:
            for identifier in jobs:
                logistra.process(self.db, self.client, {}, identifier, printing=True)
            self.assertEqual(logistra.discover_jobs(self.db, self.client), [])
            printing.assert_called_once()

    def test_pdf_not_ready_survives_discovery_window(self):
        self.client.ids.return_value = []
        logistra.discovery_baseline(self.db, self.client)
        self.client.ids.return_value = ['101']
        self.assertEqual(logistra.discover_jobs(self.db, self.client), ['101'])
        self.client.pdf.side_effect = RuntimeError('PDF not ready yet')
        with self.assertRaises(RuntimeError):
            logistra.process(self.db, self.client, {}, '101')
        self.client.ids.return_value = []
        self.assertEqual(logistra.discover_jobs(self.db, self.client), ['101'])
        self.client.pdf.side_effect = None
        logistra.process(self.db, self.client, {}, '101')
        self.assertEqual(self.db.execute("SELECT status FROM jobs WHERE id='101'").fetchone()[0], 'downloaded')

    def test_migration_preserves_history_and_skips_existing_shipments(self):
        with self.db:
            self.db.execute("INSERT INTO settings VALUES ('baseline', 'yes')")
            self.db.executemany('INSERT INTO jobs VALUES (?, ?)', [('100', 'baseline'), ('101', 'submitted'), ('102', 'uncertain')])
        self.client.ids.return_value = ['100', '101', '102', '103']
        logistra.discovery_baseline(self.db, self.client)
        self.assertEqual(logistra.discover_jobs(self.db, self.client), [])
        self.assertEqual(self.db.execute("SELECT status FROM jobs WHERE id='101'").fetchone()[0], 'submitted')
        self.assertEqual(self.db.execute("SELECT status FROM jobs WHERE id='102'").fetchone()[0], 'uncertain')
        self.assertEqual(self.db.execute("SELECT status FROM jobs WHERE id='103'").fetchone()[0], 'baseline')

    def test_catchup_and_failed_list_do_not_advance_checkpoint(self):
        old = date.today() - timedelta(days=7)
        with self.db:
            self.db.execute("INSERT INTO settings VALUES ('discovery_checkpoint', ?)", (old.isoformat(),))
        self.client.ids.side_effect = RuntimeError('incomplete page')
        with self.assertRaises(RuntimeError):
            logistra.discover_jobs(self.db, self.client)
        self.client.ids.assert_called_once_with(since=old - timedelta(days=1))
        self.assertEqual(self.db.execute("SELECT value FROM settings WHERE name='discovery_checkpoint'").fetchone()[0], old.isoformat())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)

    def test_all_states_and_complete_pagination_use_fresh_api(self):
        with patch.object(logistra, 'api_key', return_value='synthetic'):
            client = logistra.Client({'sender_id': '12345', 'list_verified': True, 'list_path': '/consignments.xml?state=open'})
        paths = []
        def get(path, fresh=False):
            paths.append((path, fresh))
            page = parse_qs(urlsplit(path).query)['page'][0]
            client.pagination = {'Total-Pages': '2', 'Total-Count': '2'}
            state, identifier = ('open', '100') if page == '1' else ('transferred', '101')
            return f'<consignments><consignment><id>{identifier}</id><state>{state}</state></consignment></consignments>'.encode()
        with patch.object(client, 'get', side_effect=get):
            self.assertEqual(client.ids(), ['100', '101'])
        self.assertEqual(len(paths), 2)
        for path, fresh in paths:
            query = parse_qs(urlsplit(path).query)
            self.assertEqual(query['state[]'], ['all'])
            self.assertNotIn('state', query)
            self.assertTrue(fresh)

    def test_cancelled_pending_shipment_is_not_printed(self):
        self.client.ids.return_value = []
        logistra.discovery_baseline(self.db, self.client)
        with self.db:
            self.db.execute("INSERT INTO jobs VALUES ('101', 'pending')")
        self.client.discovered_states = {'101': 'cancelled'}
        self.assertEqual(logistra.discover_jobs(self.db, self.client), [])
        self.assertEqual(self.db.execute("SELECT status FROM jobs WHERE id='101'").fetchone()[0], 'ignored')
