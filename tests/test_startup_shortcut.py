import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import logistra_gui as gui


@unittest.skipUnless(os.name == 'nt', 'Windows shortcut')
class ShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[1] / 'build').mkdir(exist_ok=True)

    def test_shortcut_has_name_icon_arguments_and_replaces_legacy(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build') as folder:
            root = Path(folder)
            directory = root / 'Microsoft/Windows/Start Menu/Programs/Startup'
            directory.mkdir(parents=True)
            legacy = directory / 'Logistra.vbs'
            legacy.write_text('legacy')
            with patch.dict(os.environ, {'APPDATA': str(root)}), patch.object(gui, 'ROOT', root):
                gui.configure_startup(True)
                shortcut = directory / 'Logistra Print.lnk'
                self.assertTrue(shortcut.is_file())
                self.assertFalse(legacy.exists())
                script = '$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\'' + str(shortcut).replace("'", "''") + "'); @{'target'=$s.TargetPath;'arguments'=$s.Arguments;'icon'=$s.IconLocation} | ConvertTo-Json -Compress"
                result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True, check=True, text=True)
                values = json.loads(result.stdout)
                self.assertTrue(values['target'].endswith('pythonw.exe'))
                self.assertIn('--startup', values['arguments'])
                self.assertEqual(values['icon'], str(root / 'logistra.ico') + ',0')
                gui.configure_startup(False)
                self.assertFalse(shortcut.exists())
