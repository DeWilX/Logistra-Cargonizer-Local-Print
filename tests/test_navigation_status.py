import threading
import gc
import tkinter as tk
import time
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch
import friendly_gui
from localization import Locale, install_widgets
from navigation import SectionNavigation, ScrollableSection
from tooltips import Tooltip
import ui_theme
from shipment_browser import ShipmentBrowser


class NavigationStatusTests(unittest.TestCase):
    def setUp(self):
        gc.collect()  # Dispose of earlier Tk widget cycles on the main thread.
        self.root = tk.Tk()
        self.root.geometry('700x500')

    def tearDown(self):
        for timer in self.root.tk.call('after', 'info'):
            self.root.tk.call('after', 'cancel', timer)
        self.root.destroy()

    def test_repeated_navigation_keeps_panels_mapped_and_scroll_size_stable(self):
        nav = SectionNavigation(self.root)
        nav.pack(fill='both', expand=True)
        sections = [ScrollableSection(nav) for _ in range(2)]
        for i, section in enumerate(sections):
            ttk.Label(section.body, text='Content ' + str(i)).pack()
            nav.add(section, text=str(i))
        self.root.update()
        for i in range(20):
            nav.select(i % 2)
            self.root.update_idletasks()
            self.assertTrue(all(section.winfo_ismapped() for section in sections))
            self.assertIs(nav.select(), sections[i % 2])
        with patch.object(sections[0].canvas, 'itemconfigure') as configure:
            sections[0].resize()
            sections[0].resize()
            configure.assert_not_called()

    def test_slow_macos_theme_detection_does_not_block_navigation(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def slow_detection():
            started.set()
            release.wait(3)
            finished.set()
            return True
        self.root._logistra_dark = False
        self.root._logistra_theme_mode = 'system'
        ticks = []
        try:
            with patch.object(ui_theme.sys, 'platform', 'darwin'), patch.object(ui_theme, 'system_dark_mode', side_effect=slow_detection):
                ui_theme.watch_theme(self.root)
                self.assertTrue(started.wait(1))
                self.root.after(0, lambda: ticks.append('responsive'))
                self.root.update()
                self.assertEqual(ticks, ['responsive'])
                self.assertFalse(finished.is_set())
        finally:
            release.set()
            self.assertTrue(finished.wait(1))

    def test_status_reasons_distinguish_missing_printer_and_unconfirmed_test(self):
        cfg = {'sender_id': '12345', 'printer': 'Label printer'}
        self.assertIn('nav atrasts', friendly_gui.status_explanations(cfg, [])[1])
        self.assertIn('testa druka nav apstiprināta', friendly_gui.status_explanations(cfg, ['Label printer'])[1])
        cfg['printer'] = 'Microsoft Print to PDF'
        self.assertIn('PDF eksports', friendly_gui.status_explanations(cfg, [cfg['printer']])[1])
        cfg['printer'] = ''
        self.assertIn('nav izvēlēts', friendly_gui.status_explanations(cfg, [])[1])
        self.assertIn('Tukšs saraksts nav kļūda', friendly_gui.status_explanations(cfg, [])[2])
        self.assertIn('veiksmīgi ielādēti', friendly_gui.status_explanations(cfg, [], True)[2])
        self.assertIn('ielāde neizdevās', friendly_gui.status_explanations(cfg, [], False)[2])

    def test_tooltip_updates_live_and_translates_status_text(self):
        self.root._logistra_locale = Locale('en')
        install_widgets()
        hint = tk.StringVar(self.root, 'Konts ir pārbaudīts un pieslēgts.')
        label = ttk.Label(self.root, text='Konts')
        label.pack()
        tooltip = Tooltip((label,), hint)
        callbacks = len(self.root._logistra_locale.refreshers)
        tooltip.show()
        popup_label = tooltip.window.winfo_children()[0].winfo_children()[0]
        self.assertEqual(popup_label.cget('text'), 'The account connection has been verified.')
        self.root._logistra_locale.set_language('nb')
        self.assertEqual(popup_label.cget('text'), 'Kontotilkoblingen er kontrollert.')
        tooltip.hide()
        self.assertIsNone(tooltip.window)
        self.assertEqual(len(self.root._logistra_locale.refreshers), callbacks)

    def test_large_table_yields_to_gui_and_finishes_all_rows(self):
        browser = ShipmentBrowser.__new__(ShipmentBrowser)
        browser.table = ttk.Treeview(self.root)
        browser.table.pack(fill='both', expand=True)
        browser.render_after = browser.filter_after = None
        browser.action_image = ''
        browser.start_date = Mock(get=Mock(return_value=''))
        browser.end_date = Mock(get=Mock(return_value=''))
        browser.date_entries = ((None, browser.start_date), (None, browser.end_date))
        browser.valid_dates = {}
        browser.carrier = Mock(get=Mock(return_value='Visi pārvadātāji'))
        browser.search = Mock(get=Mock(return_value=''))
        browser.notice = browser.filter_info = Mock()
        browser.loaded_period = (None, None)
        browser.rows = [{'id': str(i), 'created': '2026-10-07', 'recipient': 'Example', 'address': '', 'carrier': '', 'product': '', 'reference': '', 'items': 1, 'number': '', 'state': 'open'} for i in range(1, 501)]
        browser.render()
        self.assertEqual(len(browser.table.get_children()), 100)
        ticks = []
        self.root.after(0, lambda: ticks.append(len(browser.table.get_children())))
        deadline = time.monotonic() + 3
        while browser.render_after is not None and time.monotonic() < deadline:
            self.root.update()
        self.assertLess(ticks[0], 500)
        self.assertEqual(len(browser.table.get_children()), 500)
