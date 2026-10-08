import gc
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock

from shipment_browser import ShipmentBrowser


class LiveFilterTests(unittest.TestCase):
    def test_date_edits_search_and_clear_change_actual_table(self):
        was_enabled = gc.isenabled()
        gc.disable()
        root = tk.Tk()
        root.withdraw()
        try:
            frame = ttk.Frame(root)
            frame.pack(fill='both', expand=True)
            view = ShipmentBrowser(frame, Mock())
            view.rows = [
                {'id': str(identifier), 'created': created, 'carrier': 'PostNord', 'recipient': 'Test',
                 'address': '', 'product': '', 'reference': reference, 'items': 1, 'number': '', 'state': 'open'}
                for identifier, created, reference in [
                    (101, '2026-09-25T12:00:00Z', 'ORD-1'),
                    (102, '2026-10-02T12:00:00Z', 'ORD-2'),
                    (103, '2026-10-07T12:00:00Z', 'ORD-3')]
            ]
            def apply_pending():
                deadline = time.monotonic() + 2
                while view.filter_after is not None and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertIsNone(view.filter_after)

            view.clear()
            self.assertEqual(view.table.get_children(), ('101', '102', '103'))
            view.start_date.set('03.10.2026')
            view.end_date.set('06.10.2026')
            apply_pending()
            self.assertEqual(view.table.get_children(), ())
            self.assertIn('Rāda 0 no 3', view.filter_info.get())
            self.assertIn('25.09.2026 – 07.10.2026', view.filter_info.get())
            view.end_date.set('07.10.2026')
            apply_pending()
            self.assertEqual(view.table.get_children(), ('103',))
            view.start_date.set(' 07.10.2026 ')
            apply_pending()
            self.assertEqual(view.table.get_children(), ('103',))
            view.start_date.set('08.10.2026')
            apply_pending()
            self.assertEqual(view.table.get_children(), ('103',))
            self.assertIn('Nederīgs', view.filter_info.get())
            view.commit_date(view.start_date)
            self.assertEqual(view.start_date.get().strip(), '07.10.2026')
            view.clear()
            self.assertEqual(view.table.get_children(), ('101', '102', '103'))
            view.search.set('ORD-2')
            apply_pending()
            self.assertEqual(view.table.get_children(), ('102',))
            view.carrier.set('Other')
            view.carriers.event_generate('<<ComboboxSelected>>')
            root.update()
            self.assertEqual(view.table.get_children(), ())
        finally:
            for timer in root.tk.call('after', 'info'):
                root.tk.call('after', 'cancel', timer)
            root.destroy()
        del view, frame, root
        gc.collect()
        if was_enabled:
            gc.enable()


if __name__ == '__main__':
    unittest.main()
