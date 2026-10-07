"""Replace a verified macOS bundle after the running application exits."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shlex
import stat
import subprocess
import sys
from zipfile import ZipFile


def validate_archive(archive_path, expected_hash):
    archive_path = Path(archive_path).resolve()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
        raise ValueError('Invalid update digest.')
    with archive_path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_hash:
            raise ValueError('Atjauninājuma SHA-256 pārbaude neizdevās.')
    with ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > 20000 or sum(item.file_size for item in members) > 1024 * 1024 * 1024:
            raise ValueError('Update archive is too large.')
        names = set()
        for item in members:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or item.filename in names:
                raise ValueError('Unsafe update archive path.')
            names.add(item.filename)
            if not path.parts or path.parts[0] not in ('Logistra.app', '__MACOSX', 'LICENSE', 'README-macOS.md'):
                raise ValueError('Unexpected update archive content.')
            if stat.S_ISLNK(item.external_attr >> 16):
                link = archive.read(item).decode('utf-8')
                destination = posixpath.normpath(posixpath.join(str(path.parent), link))
                if link.startswith('/') or not destination.startswith('Logistra.app/'):
                    raise ValueError('Update symlink leaves the application bundle.')
        binary = archive.read('Logistra.app/Contents/MacOS/Logistra')
        if binary[:4] not in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'):
            raise ValueError('Update does not contain a macOS executable.')
        metadata = json.loads(archive.read('Logistra.app/Contents/Resources/release-info.json'))
        version = re.search(r'-(\d+\.\d+\.\d+)\.zip$', archive_path.name)
        if not version or metadata.get('version') != version[1]:
            raise ValueError('Update bundle version does not match its release.')
    return archive_path


def installed_bundle(executable=None):
    executable = Path(executable or sys.executable).resolve()
    bundle = executable.parent.parent.parent
    if bundle.suffix != '.app' or executable != bundle / 'Contents/MacOS/Logistra':
        raise ValueError('Run the installed Logistra.app to update it.')
    if 'AppTranslocation' in bundle.parts or 'Volumes' in bundle.parts:
        raise ValueError('Pirms atjaunināšanas pārvieto Logistra.app uz Applications mapi.')
    return bundle


def replacement_script(archive_path, target, expected_hash, parent_pid, hidden=False, resume=False, restart=True):
    archive_path, target = Path(archive_path).resolve(), Path(target).resolve()
    if target.suffix != '.app' or not target.is_dir() or not archive_path.is_file():
        raise ValueError('Update requires an existing application and archive.')
    if not isinstance(parent_pid, int) or parent_pid < 0 or not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
        raise ValueError('Invalid update parameters.')
    q = shlex.quote
    # Only these two siblings of the exact installed bundle may be moved.
    candidate = target.with_name(target.name + '.update-new')
    backup = target.with_name(target.name + '.update-backup-' + expected_hash[:12])
    script = 'set -eu\nexport PYINSTALLER_RESET_ENVIRONMENT=1\n'
    script += f'archive={q(str(archive_path))}\ntarget={q(str(target))}\ncandidate={q(str(candidate))}\nbackup={q(str(backup))}\n'
    if restart:
        script += 'trap \'/usr/bin/open -n "$target"; /usr/bin/osascript -e "display alert \\\"Logistra update failed\\\" message \\\"The original application is retained. See update.log.\\\""\' ERR\n'
    if parent_pid:
        script += f'count=0; while /bin/kill -0 {parent_pid} 2>/dev/null; do count=$((count+1)); [ "$count" -lt 180 ] || exit 1; /bin/sleep 1; done\n'
    script += f'[ "$(/usr/bin/shasum -a 256 "$archive" | /usr/bin/cut -d " " -f 1)" = {q(expected_hash)} ] || exit 1\n'
    script += '[ ! -e "$candidate" ] && [ ! -e "$backup" ] || exit 1\n'
    script += 'work=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/logistra-update.XXXXXX")\n'
    script += '/usr/bin/ditto -x -k "$archive" "$work"\n'
    script += '[ -x "$work/Logistra.app/Contents/MacOS/Logistra" ] || exit 1\n'
    # The launcher chooses administrator authorization when the parent is read-only.
    script += 'replace_bundle() {\n'
    script += '/usr/bin/ditto "$work/Logistra.app" "$candidate" || return 1\n'
    script += '/bin/mv "$target" "$backup" || return 1\n'
    script += 'if ! /bin/mv "$candidate" "$target"; then /bin/mv "$backup" "$target"; return 1; fi\n}\n'
    script += 'replace_bundle\n'
    if restart:
        arguments = '--start-hidden' if hidden else '--after-update'
        if resume:
            arguments += ' --resume-automation'
        script += f'/usr/bin/open -n "$target" --args {arguments}\n'
    # Keep the previous bundle as a recoverable backup; no recursive deletion.
    script += '/bin/echo "Update complete; previous application retained at $backup"\n'
    return script


def launch_replacement(staged, expected_hash, hidden=False, resume=False):
    archive_path = validate_archive(staged, expected_hash)
    target = installed_bundle()
    candidate = target.with_name(target.name + '.update-new')
    backup = target.with_name(target.name + '.update-backup-' + expected_hash[:12])
    if candidate.exists() or backup.exists():
        raise ValueError('Blakus lietotnei ir iepriekšējā atjauninājuma kopija. Pārvieto to pirms nākamā atjauninājuma.')
    script_path = archive_path.parent / 'replace-macos.sh'
    script = replacement_script(archive_path, target, expected_hash, os.getpid(), hidden, resume)
    if not os.access(target.parent, os.W_OK):
        # Elevate only replacement commands; restart remains in the user's session.
        start = script.index('replace_bundle()')
        end = script.index('replace_bundle\n', start) + len('replace_bundle\n')
        # Parent exit and extraction already occur in the unprivileged helper.
        elevated = f'target={shlex.quote(str(target))}; candidate={shlex.quote(str(candidate))}; backup={shlex.quote(str(backup))}; work="$1"; ' + script[start:end]
        privileged_path = archive_path.parent / 'replace-macos-privileged.sh'
        privileged_path.write_text('set -eu\n' + elevated, encoding='utf-8')
        command = '/bin/sh ' + shlex.quote(str(privileged_path))
        # Pass the generated extraction directory as shell-quoted text via argv.
        apple = 'on run argv\n do shell script (' + json.dumps(command + ' ', ensure_ascii=False) + ' & quoted form of item 1 of argv) with administrator privileges\nend run'
        apple_path = archive_path.parent / 'replace-macos.applescript'
        apple_path.write_text(apple, encoding='utf-8')
        script = script[:start] + '/usr/bin/osascript ' + shlex.quote(str(apple_path)) + ' "$work"\n' + script[end:]
    script_path.write_text(script, encoding='utf-8')
    log = (archive_path.parent / 'update.log').open('ab')
    try:
        return subprocess.Popen(['/bin/bash', str(script_path)], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True, cwd=archive_path.parent)
    finally:
        log.close()
