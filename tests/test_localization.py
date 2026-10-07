import gc
import tkinter as tk
from tkinter import ttk
import unittest
from localization import Locale, install_widgets, TRANSLATIONS


class LocalizationTests(unittest.TestCase):
    def test_dynamic_statuses_and_catalogs(self):
        self.assertEqual(Locale('en').translate('Pārbaude ik pēc 5 sekundēm'), 'Check every 5 seconds')
        self.assertEqual(Locale('nb').translate('Printeris: nav iestatīts'), 'Skriver: ikke konfigurert')
        self.assertEqual(set(TRANSLATIONS['en']), set(TRANSLATIONS['nb']))
        self.assertEqual(Locale('en').translate('ORD-123456789'), 'ORD-123456789')

    def test_language_switch_updates_labels_and_preserves_filter_model(self):
        was_enabled = gc.isenabled()
        gc.disable()
        root = tk.Tk()
        root.withdraw()
        try:
            root._logistra_locale = Locale('en')
            install_widgets()
            model = tk.StringVar(root, value='Pēdējās 30 dienas')
            combo = ttk.Combobox(root, textvariable=model, values=['Pēdējās 30 dienas', 'Pēdējās 7 dienas'], state='readonly')
            label = ttk.Label(root, text='Iestatījumi')
            status = tk.StringVar(root, value='Pārbaude ik pēc 5 sekundēm')
            status_label = ttk.Label(root, textvariable=status)
            self.assertEqual(label.cget('text'), 'Settings')
            self.assertEqual(combo.get(), 'Last 30 days')
            self.assertEqual(model.get(), 'Pēdējās 30 dienas')
            combo.set('Last 7 days')
            self.assertEqual(model.get(), 'Pēdējās 7 dienas')
            root._logistra_locale.set_language('nb')
            self.assertEqual(label.cget('text'), 'Innstillinger')
            self.assertEqual(combo.get(), 'Siste 7 dager')
            self.assertEqual(root.getvar(status_label.cget('textvariable')), 'Kontroll hvert 5. sekund')
            self.assertEqual(model.get(), 'Pēdējās 7 dienas')
            root._logistra_locale.set_language('lv')
            self.assertEqual(combo.get(), model.get())
            root.update_idletasks()
        finally:
            root.destroy()
            gc.collect()
            if was_enabled:
                gc.enable()
