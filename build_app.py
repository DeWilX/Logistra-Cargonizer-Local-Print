"""Build on the target OS; Python is included in the output."""
from pathlib import Path
import argparse
import platform
import subprocess
import ssl
import json
import os
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from version import UPDATE_REPOSITORY

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dist-dir', type=Path, default=root / 'dist')
parser.add_argument('--version', default='0.1.0')
parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY') or UPDATE_REPOSITORY)
args = parser.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
    raise SystemExit('Version must be X.Y.Z.')
release_info = root / 'build/release-info.json'
release_info.parent.mkdir(parents=True, exist_ok=True)
release_info.write_text(json.dumps({'version': args.version, 'repository': args.repository}), encoding='utf-8')
dist = args.dist_dir.resolve()
if sys.platform not in ('win32', 'darwin'):
    raise SystemExit('Build on Windows or macOS; cross compilation is not supported.')
app_name = 'Logistra-Print' if sys.platform == 'win32' else 'Logistra'
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', app_name, '--distpath', str(dist),
           '--add-data', str(root / 'config.defaults.json') + ':.', '--add-data', str(release_info) + ':.', '--add-data', str(root / 'assets') + ':assets', '--hidden-import', 'mac_support',
           '--icon', str(root / 'assets' / ('logistra.icns' if sys.platform == 'darwin' else 'logistra.ico'))]
certificate = ssl.get_default_verify_paths().cafile
if certificate:
    # macOS Python may refer to a certificate file outside the application bundle.
    bundled_certificate = root / 'build' / 'certificates' / 'cacert.pem'
    bundled_certificate.parent.mkdir(parents=True, exist_ok=True)
    bundled_certificate.write_bytes(Path(certificate).read_bytes())
    command += ['--add-data', str(bundled_certificate) + ':.']
if sys.platform == 'win32':
    command += ['--onefile', '--hidden-import', 'pystray._win32']
else:
    command += ['--onedir', '--osx-bundle-identifier', 'app.logistra.print']
command += [str(root / 'logistra_gui.py')]
subprocess.run(command, cwd=root, check=True)
if sys.platform == 'darwin':
    target = dist / f'Logistra-macOS-{platform.machine()}.zip'
    subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(dist / 'Logistra.app'), str(target)], check=True)
else:
    target = dist / 'Logistra-Windows-exe.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        archive.write(dist / f'{app_name}.exe', f'{app_name}.exe')
        instructions = root / 'LIETOSANA-Windows.txt'
        if instructions.is_file():
            archive.write(instructions, instructions.name)
print(target)
