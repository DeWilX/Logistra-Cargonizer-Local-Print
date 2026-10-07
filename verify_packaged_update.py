"""Exercise replacement and restart of an actual packaged app in an isolated folder."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from version import VERSION


def verify():
    workspace = Path(__file__).resolve().parent
    (workspace / 'build').mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='packaged-update-', dir=workspace / 'build')).resolve()
    assert folder.is_relative_to(workspace / 'build')
    data = folder / 'user-data'
    data.mkdir()
    shutil.copy2(workspace / 'config.defaults.json', data / 'config.json')
    before = (data / 'config.json').read_bytes()
    report = folder / 'restarted.json'
    environment = {**os.environ, 'LOGISTRA_DATA_DIR': str(data)}
    environment.pop('CARGONIZER_API_KEY', None)
    if sys.platform == 'win32':
        staged, target = folder / 'staged.exe', folder / 'Logistra-Print.exe'
        shutil.copy2(workspace / 'dist/Logistra-Print.exe', staged)
        shutil.copy2(staged, target)
        # Start the actual frozen/windowed app. It must launch the helper itself,
        # exit, be replaced, then restart to produce the report. Running just the
        # PowerShell script from Python misses console creation flag failures.
        subprocess.run([str(target), '--self-test', '--self-test-update', str(staged),
                        '--self-test-report', str(report)], env=environment, check=True, timeout=30)
        deadline = time.monotonic() + 60
        while not report.is_file() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert report.is_file(), 'Restart failed: ' + (folder / 'update.log').read_text(errors='replace')
        assert target.read_bytes() == staged.read_bytes()
        assert target.with_name(target.name + '.bak').read_bytes() == staged.read_bytes()
    elif sys.platform == 'darwin':
        from mac_updater import validate_archive, replacement_script
        target = folder / 'Logistra.app'
        subprocess.run(['/usr/bin/ditto', str(workspace / 'dist/Logistra.app'), str(target)], check=True)
        staged = folder / f'Logistra-macOS-{platform.machine()}-{VERSION}.zip'
        shutil.copy2(workspace / f'dist/Logistra-macOS-{platform.machine()}.zip', staged)
        digest = hashlib.sha256(staged.read_bytes()).hexdigest()
        validate_archive(staged, digest)
        script = replacement_script(staged, target, digest, 0, restart=False)
        subprocess.run(['/bin/bash', '-c', script], env=environment, check=True, timeout=90)
        assert target.with_name(target.name + '.update-backup-' + digest[:12]).is_dir()
        subprocess.run([str(target / 'Contents/MacOS/Logistra'), '--self-test', '--self-test-report', str(report)],
                       env=environment, check=True, timeout=90)
    else:
        raise RuntimeError('Run on the packaged application platform.')
    assert json.loads(report.read_text())['frozen']
    assert (data / 'config.json').read_bytes() == before
    print('Packaged replacement, restart and configuration preservation passed.')


if __name__ == '__main__':
    verify()
