"""Verified public GitHub release downloads and a Windows replacement helper."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error
from version import VERSION

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


def validate_release(payload, repository, current=VERSION):
    repository = repository_name(repository)
    if payload.get('draft') or payload.get('prerelease'):
        return None
    tag = payload['tag_name']
    if version_tuple(tag) <= version_tuple(current):
        return None
    asset = next((item for item in payload.get('assets', []) if item.get('name') == 'Logistra-Print.exe' and item.get('state') == 'uploaded'), None)
    if not asset:
        raise ValueError('GitHub laidienā nav gatava Windows EXE.')
    url = asset.get('browser_download_url', '')
    parsed = urllib.parse.urlsplit(url)
    expected = '/' + repository + '/releases/download/' + tag + '/Logistra-Print.exe'
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


def check_release(repository, current=VERSION):
    repository = repository_name(repository)
    request = urllib.request.Request(f'https://api.github.com/repos/{repository}/releases/latest',
                                    headers={'Accept': 'application/vnd.github+json',
                                             'User-Agent': 'Logistra-Print/' + current,
                                             'X-GitHub-Api-Version': '2026-03-10'})
    try:
        with urllib.request.build_opener(GitHubRedirect()).open(request, timeout=30) as response:
            body = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ValueError('GitHub laidieni vēl nav publicēti vai repozitorijs nav publisks.') from None
        raise ValueError(f'GitHub HTTP {error.code}.') from None
    if len(body) > 1024 * 1024:
        raise ValueError('GitHub atbilde ir pārāk liela.')
    return validate_release(json.loads(body), repository, current)


def download_release(release, directory, opener=None):
    # Recheck the trust boundary even if called with a forged result dictionary.
    validated = validate_release({'tag_name': 'v' + release['version'], 'assets': [{
        'name': 'Logistra-Print.exe', 'state': 'uploaded', 'browser_download_url': release['url'],
        'digest': 'sha256:' + release['sha256'], 'size': release['size']}]}, release['repository'], '0.0.0')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ('Logistra-Print-' + validated['version'] + '.exe')
    temporary = target.with_suffix('.part')
    request = urllib.request.Request(validated['url'], headers={'User-Agent': 'Logistra-Print/' + VERSION})
    opener = opener or urllib.request.build_opener(GitHubRedirect())
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
            if stream.read(2) != b'MZ':
                raise ValueError('Atjauninājums nav Windows EXE.')
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
    script += 'Start-Process -FilePath $target -ArgumentList ' + quote(arguments) + ' -WorkingDirectory ' + quote(target.parent) + ' -WindowStyle Hidden'
    return script


def launch_replacement(staged, expected_hash, hidden=False, resume=False):
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        raise ValueError('Automātiska EXE aizstāšana pieejama Windows EXE versijā.')
    script = replacement_script(staged, sys.executable, expected_hash, os.getpid(), hidden, resume)
    # Persist diagnostics beside the staged download, never in user shipment data.
    log = Path(staged).parent / 'update.log'
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = 'try { ' + script + ' } catch { $_ | Out-File -LiteralPath ' + quote(log) + ' -Encoding utf8; exit 1 }'
    return subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                             base64.b64encode(script.encode('utf-16le')).decode('ascii')],
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
