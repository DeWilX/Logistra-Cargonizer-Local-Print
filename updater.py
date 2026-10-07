"""Verified public GitHub release downloads and a Windows replacement helper."""
import base64
import hashlib
from html.parser import HTMLParser
import json
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error
from version import VERSION
from network_tls import verified_context

MAX_EXE_SIZE = 200 * 1024 * 1024


def repository_name(value):
    value = value.strip().rstrip('/')
    if value.startswith('https://github.com/'):
        value = value[len('https://github.com/'):]
    value = value.removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', value) or '..' in value:
        raise ValueError('Ievadi GitHub repozitoriju owner/repo vai tā HTTPS saiti.')
    return value


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    if not match:
        raise ValueError('Atjauninājuma versijai jābūt X.Y.Z.')
    return tuple(int(part) for part in match.groups())


def platform_asset():
    if sys.platform == 'darwin':
        arch = platform.machine().lower()
        if arch not in ('arm64', 'x86_64'):
            raise ValueError('Unsupported Mac architecture.')
        return 'Logistra-macOS-' + arch + '.zip'
    return 'Logistra-Print.exe'


def validate_release(payload, repository, current=VERSION, asset_name='Logistra-Print.exe'):
    repository = repository_name(repository)
    if payload.get('draft') or payload.get('prerelease'):
        return None
    tag = payload['tag_name']
    if version_tuple(tag) <= version_tuple(current):
        return None
    if asset_name not in ('Logistra-Print.exe', 'Logistra-macOS-arm64.zip', 'Logistra-macOS-x86_64.zip'):
        raise ValueError('Unsupported release asset.')
    asset = next((item for item in payload.get('assets', []) if item.get('name') == asset_name and item.get('state') == 'uploaded'), None)
    if not asset:
        raise ValueError('GitHub laidienā nav gatava Windows EXE.')
    url = asset.get('browser_download_url', '')
    parsed = urllib.parse.urlsplit(url)
    expected = '/' + repository + '/releases/download/' + tag + '/' + asset_name
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.path != expected or parsed.query or parsed.fragment:
        raise ValueError('Atjauninājuma saite neatbilst izvēlētajam GitHub repozitorijam.')
    digest = asset.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
        raise ValueError('GitHub laidienam nav SHA-256 pārbaudes vērtības.')
    size = asset.get('size')
    if not isinstance(size, int) or not 2 <= size <= MAX_EXE_SIZE:
        raise ValueError('Atjauninājuma izmērs nav derīgs.')
    return {'version': tag.removeprefix('v'), 'repository': repository, 'url': url,
            'sha256': digest.split(':')[1].lower(), 'size': size}


class GitHubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.netloc not in ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'):
            raise ValueError('Atjauninājuma novirzīšana nav uz GitHub lejupielādes serveri.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def github_opener():
    return urllib.request.build_opener(GitHubRedirect(), urllib.request.HTTPSHandler(context=verified_context()))


class ReleaseAssetParser(HTMLParser):
    """Read the digest and download link belonging to the same release asset row."""
    def __init__(self, expected):
        super().__init__()
        self.expected = expected
        self.row = None
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li':
            self.row = {}
        elif self.row is not None:
            if tag == 'a' and attrs.get('href') == self.expected:
                self.row['url'] = 'https://github.com' + self.expected
            if tag == 'clipboard-copy' and attrs.get('aria-label') == 'Copy to clipboard digest for ' + self.expected.rsplit('/', 1)[-1]:
                self.row['digest'] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'li' and self.row is not None:
            if 'url' in self.row:
                self.assets.append(self.row)
            self.row = None


def check_release_page(repository, current=VERSION, opener=None, asset_name='Logistra-Print.exe'):
    """Official release page fallback when GitHub's public API is rate limited."""
    repository = repository_name(repository)
    opener = opener or github_opener()
    headers = {'User-Agent': 'Logistra-Print/' + current}
    with opener.open(urllib.request.Request(f'https://github.com/{repository}/releases/latest', headers=headers), timeout=30) as response:
        latest = urllib.parse.urlsplit(response.geturl())
    prefix = '/' + repository + '/releases/tag/'
    if latest.scheme != 'https' or latest.netloc != 'github.com' or not latest.path.startswith(prefix) or latest.query or latest.fragment:
        raise ValueError('Atjauninājuma saite neatbilst izvēlētajam GitHub repozitorijam.')
    tag = latest.path[len(prefix):]
    if version_tuple(tag) <= version_tuple(current):
        return None
    with opener.open(urllib.request.Request(f'https://github.com/{repository}/releases/expanded_assets/{tag}', headers=headers), timeout=30) as response:
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError('GitHub atbilde ir pārāk liela.')
    expected = '/' + repository + '/releases/download/' + tag + '/' + asset_name
    parser = ReleaseAssetParser(expected)
    parser.feed(body.decode('utf-8'))
    if len(parser.assets) != 1:
        raise ValueError('GitHub laidienā nav gatava Windows EXE.')
    asset = parser.assets[0]
    # Validate the digest before requesting the executable's size.
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', asset.get('digest', '')):
        raise ValueError('GitHub laidienam nav SHA-256 pārbaudes vērtības.')
    with opener.open(urllib.request.Request(asset['url'], headers=headers, method='HEAD'), timeout=30) as response:
        size = int(response.headers.get('Content-Length', '0'))
    return validate_release({'tag_name': tag, 'assets': [{'name': asset_name, 'state': 'uploaded',
        'browser_download_url': asset['url'], 'digest': asset['digest'], 'size': size}]}, repository, current, asset_name)


def check_release(repository, current=VERSION, asset_name='Logistra-Print.exe'):
    repository = repository_name(repository)
    request = urllib.request.Request(f'https://api.github.com/repos/{repository}/releases/latest',
                                    headers={'Accept': 'application/vnd.github+json',
                                             'User-Agent': 'Logistra-Print/' + current,
                                             'X-GitHub-Api-Version': '2026-03-10'})
    try:
        with github_opener().open(request, timeout=30) as response:
            body = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        if error.code == 429 or error.code == 403 and (error.headers.get('X-RateLimit-Remaining') == '0' or error.headers.get('Retry-After')):
            if asset_name == 'Logistra-Print.exe':
                return check_release_page(repository, current)
            return check_release_page(repository, current, asset_name=asset_name)
        if error.code == 404:
            raise ValueError('GitHub laidieni vēl nav publicēti vai repozitorijs nav publisks.') from None
        raise ValueError(f'GitHub HTTP {error.code}.') from None
    if len(body) > 1024 * 1024:
        raise ValueError('GitHub atbilde ir pārāk liela.')
    return validate_release(json.loads(body), repository, current, asset_name)


def download_release(release, directory, opener=None):
    # Recheck the trust boundary even if called with a forged result dictionary.
    asset_name = urllib.parse.urlsplit(release['url']).path.rsplit('/', 1)[-1]
    validated = validate_release({'tag_name': 'v' + release['version'], 'assets': [{
        'name': asset_name, 'state': 'uploaded', 'browser_download_url': release['url'],
        'digest': 'sha256:' + release['sha256'], 'size': release['size']}]}, release['repository'], '0.0.0', asset_name)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (Path(asset_name).stem + '-' + validated['version'] + Path(asset_name).suffix)
    temporary = target.with_suffix('.part')
    request = urllib.request.Request(validated['url'], headers={'User-Agent': 'Logistra-Print/' + VERSION})
    opener = opener or github_opener()
    digest = hashlib.sha256()
    size = 0
    try:
        with opener.open(request, timeout=45) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > validated['size']:
                    raise ValueError('Lejupielādētais EXE pārsniedz norādīto izmēru.')
                digest.update(chunk)
                stream.write(chunk)
        if size != validated['size'] or digest.hexdigest() != validated['sha256']:
            raise ValueError('Atjauninājuma SHA-256 vai izmēra pārbaude neizdevās.')
        with temporary.open('rb') as stream:
            magic = stream.read(4)
            if asset_name.endswith('.exe') and magic[:2] != b'MZ' or asset_name.endswith('.zip') and magic != b'PK\x03\x04':
                raise ValueError('Atjauninājuma faila formāts nav derīgs.')
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def replacement_script(staged, target, expected_hash, parent_pid, hidden=False, resume=False):
    staged, target = Path(staged).resolve(), Path(target).resolve()
    if staged == target or target.suffix.lower() != '.exe' or not staged.is_file() or not target.is_file():
        raise ValueError('Atjaunināšanai vajadzīgi atšķirīgi esoši EXE faili.')
    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected_hash) or not isinstance(parent_pid, int) or parent_pid < 0:
        raise ValueError('Atjauninājuma pārbaudes parametri nav derīgi.')
    replacement = target.with_name(target.name + '.new')
    backup = target.with_name(target.name + '.bak')
    # Every mutation stays in the explicitly selected executable's directory.
    for path in (replacement, backup):
        if path.parent != target.parent:
            raise ValueError('Nederīgs atjauninājuma ceļš.')
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = '$ErrorActionPreference="Stop"; '
    script += 'Import-Module ($PSHOME + "\\Modules\\Microsoft.PowerShell.Management\\Microsoft.PowerShell.Management.psd1"); '
    script += 'Import-Module ($PSHOME + "\\Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1"); '
    script += f'$source={quote(staged)}; $target={quote(target)}; $replacement={quote(replacement)}; $backup={quote(backup)}; '
    script += '$expected=' + quote(expected_hash) + '; '
    if parent_pid:
        script += f'if (Get-Process -Id {parent_pid} -ErrorAction SilentlyContinue) {{ Wait-Process -Id {parent_pid} -Timeout 180 }}; '
    script += 'if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $expected) { throw "Update hash mismatch" }; '
    script += 'Copy-Item -LiteralPath $source -Destination $replacement -Force; '
    script += 'if ((Get-FileHash -LiteralPath $replacement -Algorithm SHA256).Hash -ne $expected) { throw "Copy hash mismatch" }; '
    script += '$done=$false; for ($attempt=0; $attempt -lt 40; $attempt++) { try { '
    script += '[System.IO.File]::Replace($replacement,$target,$backup,$true); $done=$true; break } catch { Start-Sleep -Milliseconds 250 } }; '
    script += 'if (-not $done) { throw "Could not replace executable; original remains unchanged" }; '
    arguments = '--start-hidden' if hidden else '--after-update'
    if resume:
        arguments += ' --resume-automation'
    # A frozen process inherits the old onefile extraction directory. Force a
    # fresh independent bootloader run after the old process removes that folder.
    script += '$env:PYINSTALLER_RESET_ENVIRONMENT="1"; '
    script += 'Start-Process -FilePath $target -ArgumentList ' + quote(arguments) + ' -WorkingDirectory ' + quote(target.parent) + ' -WindowStyle Hidden'
    return script


def launch_replacement(staged, expected_hash, hidden=False, resume=False):
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        from mac_updater import launch_replacement as launch_mac
        return launch_mac(staged, expected_hash, hidden, resume)
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        raise ValueError('Automātiska EXE aizstāšana pieejama Windows EXE versijā.')
    script = replacement_script(staged, sys.executable, expected_hash, os.getpid(), hidden, resume)
    # Persist diagnostics beside the staged download, never in user shipment data.
    log = Path(staged).parent / 'update.log'
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = 'try { ' + script + ' } catch { $_ | Out-File -LiteralPath ' + quote(log) + ' -Encoding utf8; '
    script += 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("Update failed. Open Logistra again. Details: " + ' + quote(log) + ', "Logistra Print"); exit 1 }'
    return subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                             base64.b64encode(script.encode('utf-16le')).decode('ascii')],
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                            env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'},
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
