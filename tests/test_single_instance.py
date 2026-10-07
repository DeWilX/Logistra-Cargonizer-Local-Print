import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from single_instance import WindowsInstance


@unittest.skipUnless(os.name == 'nt', 'Windows named mutex and event')
class SingleInstanceTests(unittest.TestCase):
    def test_second_process_notifies_first_and_exits_without_becoming_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            first = WindowsInstance(directory)
            try:
                self.assertTrue(first.primary)
                script = 'from single_instance import WindowsInstance; import sys; instance=WindowsInstance(sys.argv[1]); assert not instance.primary; instance.notify(); instance.close()'
                result = subprocess.run([sys.executable, '-c', script, directory], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(first.requested())
                self.assertFalse(first.requested())
            finally:
                first.close()
            restarted = WindowsInstance(directory)
            try:
                self.assertTrue(restarted.primary)
            finally:
                restarted.close()

    def test_different_user_data_directories_do_not_block_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            first = WindowsInstance(Path(directory) / 'first')
            second = WindowsInstance(Path(directory) / 'second')
            try:
                self.assertTrue(first.primary)
                self.assertTrue(second.primary)
            finally:
                first.close()
                second.close()
