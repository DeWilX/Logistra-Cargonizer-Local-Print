"""Current-user DPAPI storage compatible with PowerShell SecureString files."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


class DataBlob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def crypt_data(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Windows DPAPI is only available on Windows.')
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.POINTER(DataBlob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = DataBlob(len(data), buffer)
    output = DataBlob()
    try:
        # No machine-wide flag or additional entropy: same scope as SecureString.
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
            raise RuntimeError('Windows DPAPI operation failed for the current user.')
        return ctypes.string_at(output.data, output.size)
    finally:
        ctypes.memset(buffer, 0, len(data))
        if output.data:
            ctypes.memset(output.data, 0, output.size)
            kernel.LocalFree(output.data)


def save_windows_key(path, value):
    value = value.strip()
    if not value:
        raise ValueError('Ievadi API atslēgu.')
    encrypted = crypt_data(value.encode('utf-16-le'))
    path = Path(path)
    temporary = path.with_suffix('.dpapi.tmp')
    temporary.write_text(encrypted.hex() + '\n', encoding='ascii')
    temporary.replace(path)


def read_windows_key(path):
    try:
        raw = Path(path).read_bytes()
        text = raw.decode('utf-16') if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else raw.decode('utf-8-sig')
        key = crypt_data(bytes.fromhex(text.strip()), decrypt=True).decode('utf-16-le').strip()
        if not key:
            raise ValueError('Empty key')
        return key
    except (OSError, ValueError, RuntimeError):
        raise RuntimeError('Neizdevās nolasīt API atslēgu. Saglabā to lietotnē ar pašreizējo Windows lietotāju.') from None
