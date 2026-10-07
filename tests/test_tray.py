import os
import gc
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk
import unittest
import json
from unittest.mock import Mock, patch

from tray_support import WindowsTray
from ui_theme import apply_theme
from friendly_gui import FriendlyApp


@unittest.skipUnless(os.name == 'nt' and not os.environ.get('GITHUB_ACTIONS'), 'Requires interactive Windows desktop')
class WindowsDesktopTests(unittest.TestCase):
    def setUp(self):
        # Destroyed Tcl interpreters must be collected on the Tk test thread,
        # rather than during allocations in a later printer/tray worker.
        self.gc_enabled = gc.isenabled()
        gc.disable()
        self.key_patch = patch('friendly_gui.engine.api_key', side_effect=RuntimeError('No test key'))
        self.key_patch.start()

    def tearDown(self):
        self.key_patch.stop()
        gc.collect()
        if self.gc_enabled:
            gc.enable()

    def finish_printer_refresh(self, root, app):
        deadline = time.monotonic() + 5
        while app.printer_ui.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        self.assertFalse(app.printer_ui.busy)

    def test_manual_launch_stays_visible_with_persistent_tray_and_pdf_folder_button(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.defaults.json').read_text())
        config['autostart'] = True
        config['check_updates_on_start'] = False
        config['close_to_tray'] = True
        root = tk.Tk()
        try:
            with patch('friendly_gui.read_config', return_value=config), patch('friendly_gui.sys.argv', ['Logistra.exe']), patch.object(FriendlyApp, 'start') as start, patch.object(FriendlyApp, 'open_folder') as open_folder:
                app = FriendlyApp(root)
                self.assertEqual(str(app.shipments_browser.table.cget('selectmode')), 'extended')
                deadline = time.monotonic() + 3
                while (not app.tray.ready or not app.tray.icon.visible) and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertTrue(app.tray.icon.visible)
                self.assertEqual(root.state(), 'normal')
                start.assert_not_called()
                app.tabs.select(1)
                root.update_idletasks()
                folder_buttons = []
                def collect(widget):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and child.cget('text') == 'Atvērt PDF mapi':
                            folder_buttons.append(child)
                        collect(child)
                collect(app.tabs.items[1][0])
                self.assertEqual(len(folder_buttons), 1)
                folder_buttons[0].invoke()
                open_folder.assert_called_once()
                app.close()
                self.assertEqual(root.state(), 'withdrawn')
                app.tray.icon()
                deadline = time.monotonic() + 3
                while root.state() != 'normal' and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertEqual(root.state(), 'normal')
                self.assertTrue(app.tray.icon.visible)
        finally:
            if 'app' in locals():
                self.finish_printer_refresh(root, app)
            for timer in root.tk.call('after', 'info'):
                root.tk.call('after', 'cancel', timer)
            root.destroy()

    def test_windows_startup_hides_in_tray_and_starts_worker(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.defaults.json').read_text())
        config['autostart'] = True
        config['check_updates_on_start'] = False
        config['theme'] = 'light'
        root = tk.Tk()
        root.withdraw()
        try:
            with patch('friendly_gui.read_config', return_value=config), patch('friendly_gui.sys.argv', ['Logistra.exe', '--startup']), patch.object(FriendlyApp, 'start') as start:
                app = FriendlyApp(root)
                deadline = time.monotonic() + 4
                while (app.tray is None or not app.tray.ready or not start.called) and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                self.assertIsNotNone(app.tray)
                self.assertTrue(app.tray.icon.visible)
                self.assertEqual(root.state(), 'withdrawn')
                self.assertFalse(root._logistra_dark)
                start.assert_called_once()
                texts = []
                def collect(widget):
                    for child in widget.winfo_children():
                        if isinstance(child, (ttk.Button, ttk.Checkbutton)):
                            texts.append(child.cget('text'))
                        collect(child)
                collect(root)
                self.assertIn('Aizverot logu, turpināt system tray', texts)
                self.assertIn('Palaist pēc Windows pieteikšanās (system tray)', texts)
                self.assertNotIn('Turpināt fonā', texts)
                self.assertNotIn('Pievienot PDF', texts)
        finally:
            if 'app' in locals():
                self.finish_printer_refresh(root, app)
            for timer in root.tk.call('after', 'info'):
                root.tk.call('after', 'cancel', timer)
            root.destroy()

    def test_real_tray_hide_restore_repeat_and_exit_on_tk_thread(self):
        root = tk.Tk()
        root.withdraw()
        exits = []
        errors = []
        tray = WindowsTray(root, Path(__file__).resolve().parents[1] / 'assets/logistra.ico',
                           lambda: exits.append(threading.get_ident()), errors.append)
        def wait_for(condition):
            until = time.monotonic() + 5
            while not condition() and time.monotonic() < until:
                root.update()
                time.sleep(0.01)
            self.assertTrue(condition())
        try:
            tray.hide()
            wait_for(lambda: tray.ready and tray.icon.visible)
            self.assertEqual(root.state(), 'withdrawn')
            tray.icon()  # Actual default menu callback, same as left click.
            wait_for(lambda: root.state() == 'normal')
            self.assertTrue(tray.icon.visible)
            tray.hide()
            self.assertEqual(root.state(), 'withdrawn')
            self.assertTrue(tray.icon.visible)
            list(tray.icon.menu.items)[-1](tray.icon)
            wait_for(lambda: bool(exits))
            self.assertEqual(exits, [threading.get_ident()])
            self.assertEqual(errors, [])
        finally:
            for timer in root.tk.call('after', 'info'):
                root.tk.call('after', 'cancel', timer)
            root.destroy()
        self.assertTrue(tray.closed)
        self.assertFalse(tray.icon._running)

    def test_active_controls_readable_after_dark_light_switch(self):
        root = tk.Tk()
        root.withdraw()
        try:
            for dark, text, background in [(True, '#e5ebf5', '#303d53'), (False, '#243247', '#edf3ff'), (True, '#e5ebf5', '#303d53')]:
                style = apply_theme(root, dark)
                for control in ['TCheckbutton', 'TRadiobutton']:
                    self.assertEqual(style.lookup(control, 'foreground', ('active',)), text)
                    self.assertEqual(style.lookup(control, 'background', ('active',)), background)
                for states in [(), ('readonly',), ('active',), ('pressed',)]:
                    self.assertEqual(style.lookup('TCombobox', 'arrowcolor', states), text)
        finally:
            for timer in root.tk.call('after', 'info'):
                root.tk.call('after', 'cancel', timer)
            root.destroy()


class TrayExitTests(unittest.TestCase):
    def test_theme_choice_saves_and_applies_immediately(self):
        app = FriendlyApp.__new__(FriendlyApp)
        app.root = Mock()
        app.theme_labels = {'system': 'Sistēmas tēma', 'light': 'Gaišs', 'dark': 'Tumšs'}
        app.theme = Mock()
        app.theme.get.return_value = 'Tumšs'
        with patch('friendly_gui.write_config') as write, patch('friendly_gui.set_theme_mode') as apply:
            app.save_theme()
        write.assert_called_once_with({'theme': 'dark'})
        apply.assert_called_once_with(app.root, 'dark')

    def test_window_close_goes_to_tray_even_when_idle(self):
        app = FriendlyApp.__new__(FriendlyApp)
        app.closing = False
        app.close_to_tray = Mock()
        app.close_to_tray.get.return_value = True
        app.hide_to_tray = Mock()
        app.exit_application = Mock()
        with patch('friendly_gui.sys.platform', 'win32'):
            app.close()
        app.hide_to_tray.assert_called_once()
        app.exit_application.assert_not_called()

    def test_unchecked_close_exits_without_background_prompt(self):
        app = FriendlyApp.__new__(FriendlyApp)
        app.closing = False
        app.close_to_tray = Mock()
        app.close_to_tray.get.return_value = False
        app.hide_to_tray = Mock()
        app.exit_application = Mock()
        with patch('friendly_gui.sys.platform', 'win32'), patch('friendly_gui.messagebox.askyesnocancel') as prompt:
            app.close()
        app.exit_application.assert_called_once()
        app.hide_to_tray.assert_not_called()
        prompt.assert_not_called()

    def test_close_preference_saves_only_that_option_while_worker_runs(self):
        app = FriendlyApp.__new__(FriendlyApp)
        app.close_to_tray = Mock()
        app.close_to_tray.get.return_value = False
        app.worker = Mock()
        with patch('friendly_gui.write_config') as write:
            app.save_close_preference()
        write.assert_called_once_with({'close_to_tray': False})

    def test_exit_waits_for_worker_without_background_prompt(self):
        app = FriendlyApp.__new__(FriendlyApp)
        app.root = Mock()
        app.worker = Mock()
        app.worker.is_alive.return_value = True
        app.task_busy = False
        app.printer_ui = Mock(busy=False)
        app.stop_worker = Mock()
        app.log = Mock()
        app.exit_application()
        self.assertTrue(app.closing)
        app.stop_worker.assert_called_once()
        app.root.destroy.assert_not_called()

    def test_exit_destroys_idle_window(self):
        app = FriendlyApp.__new__(FriendlyApp)
        app.root = Mock()
        app.worker = None
        app.task_busy = False
        app.printer_ui = Mock(busy=False)
        app.exit_application()
        app.root.destroy.assert_called_once()
