import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import logistra
import logistra_gui


class GuiWorkerTests(unittest.TestCase):
    def test_missing_baseline_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(logistra, 'ROOT', Path(folder)):
            app = logistra_gui.App.__new__(logistra_gui.App)
            app.events = queue.Queue()
            app.stop = threading.Event()
            app.watch({})
            messages = []
            while not app.events.empty():
                messages.append(app.events.get()[1])
            self.assertIn('sākuma atskaiti', messages[0])
            self.assertEqual(messages[-1], 'Automātika apturēta')

    def test_download_only_worker_and_graceful_stop(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(logistra, 'ROOT', Path(folder)):
            (Path(folder) / 'data').mkdir()
            db = logistra.database()
            db.execute("INSERT INTO settings VALUES ('baseline', 'yes')")
            db.commit()
            db.close()
            app = logistra_gui.App.__new__(logistra_gui.App)
            app.events = queue.Queue()
            app.stop = threading.Event()
            client = Mock()
            client.ids.return_value = ['123']
            def pdf(_):
                app.stop.set()
                return b'%PDF-1.4\nmock'
            client.pdf.side_effect = pdf
            with patch.object(logistra, 'Client', return_value=client), patch.object(logistra, 'print_pdf') as printer:
                app.watch({'auto_print': False, 'poll_seconds': 5})
                printer.assert_not_called()
            db = logistra.database()
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id="123"').fetchone()[0], 'downloaded')
            db.close()

    def test_config_update_preserves_printer(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(logistra_gui, 'ROOT', Path(folder)):
            path = Path(folder) / 'config.json'
            path.write_text('{"printer":"Zebra","sender_id":"12345"}')
            cfg = logistra_gui.write_config({'poll_seconds': 15})
            self.assertEqual(cfg['printer'], 'Zebra')
            self.assertEqual(cfg['sender_id'], '12345')


if __name__ == '__main__':
    unittest.main()
