import unittest
from unittest.mock import Mock, patch
import ui_theme
import tkinter as tk
from ui_theme import window_geometry


class WindowSizeTests(unittest.TestCase):
    def test_manual_theme_stays_fixed_and_system_mode_follows_changes(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(ui_theme, 'system_dark_mode', return_value=True):
                ui_theme.set_theme_mode(root, 'light')
                ui_theme.watch_theme(root)
                self.assertFalse(root._logistra_dark)
                ui_theme.set_theme_mode(root, 'system')
                self.assertTrue(root._logistra_dark)
            with patch.object(ui_theme, 'system_dark_mode', return_value=False):
                ui_theme.watch_theme(root)
                self.assertFalse(root._logistra_dark)
                ui_theme.set_theme_mode(root, 'dark')
                ui_theme.watch_theme(root)
                self.assertTrue(root._logistra_dark)
        finally:
            for timer in root.tk.call('after', 'info'):
                root.tk.call('after', 'cancel', timer)
            root.destroy()

    def test_macos_dark_detection(self):
        with patch.object(ui_theme.sys, 'platform', 'darwin'), patch.object(ui_theme.subprocess, 'run', return_value=Mock(returncode=0, stdout='Dark\n')):
            self.assertTrue(ui_theme.system_dark_mode())

    def test_missing_macos_setting_defaults_to_light(self):
        with patch.object(ui_theme.sys, 'platform', 'darwin'), patch.object(ui_theme.subprocess, 'run', return_value=Mock(returncode=1, stdout='')):
            self.assertFalse(ui_theme.system_dark_mode())

    def test_windows_dark_detection(self):
        registry = Mock()
        registry.QueryValueEx.return_value = (0, 4)
        registry.OpenKey.return_value = Mock(__enter__=Mock(return_value='key'), __exit__=Mock(return_value=False))
        with patch.object(ui_theme.sys, 'platform', 'win32'), patch.dict('sys.modules', winreg=registry):
            self.assertTrue(ui_theme.system_dark_mode())

    def test_laptop_fits_screen(self):
        width, height, x, y = window_geometry(1440, 900)
        self.assertEqual((width, height), (1376, 800))
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(height + y, 900)

    def test_large_monitor_uses_wide_table(self):
        self.assertEqual(window_geometry(1920,1080)[:2], (1530,920))
