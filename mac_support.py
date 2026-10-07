"""Native macOS Keychain storage, without a password in process arguments."""
import ctypes
import sys
import threading

SERVICE = b'Logistra Cargonizer'
ACCOUNT = b'api-key'
_cached_key = None
_key_lock = threading.Lock()


def security_api():
    if sys.platform != 'darwin':
        raise RuntimeError('macOS Keychain is only available on macOS.')
    api = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
    ptr = ctypes.c_void_p
    uint = ctypes.c_uint32
    api.SecKeychainFindGenericPassword.argtypes = [ptr, uint, ptr, uint, ptr, ctypes.POINTER(uint), ctypes.POINTER(ptr), ctypes.POINTER(ptr)]
    api.SecKeychainAddGenericPassword.argtypes = [ptr, uint, ptr, uint, ptr, uint, ptr, ctypes.POINTER(ptr)]
    api.SecKeychainItemModifyAttributesAndData.argtypes = [ptr, ptr, uint, ptr]
    api.SecKeychainItemFreeContent.argtypes = [ptr, ptr]
    for name in ('SecKeychainFindGenericPassword', 'SecKeychainAddGenericPassword', 'SecKeychainItemModifyAttributesAndData', 'SecKeychainItemFreeContent'):
        getattr(api, name).restype = ctypes.c_int32
    return api


def keychain_key(value=None):
    global _cached_key
    with _key_lock:
        if value is None and _cached_key is not None:
            return _cached_key
        result = _keychain_key(value)
        _cached_key = result if value is None else value.strip()
        return result


def _keychain_key(value=None):
    api = security_api()
    length = ctypes.c_uint32()
    data = ctypes.c_void_p()
    item = ctypes.c_void_p()
    result = api.SecKeychainFindGenericPassword(None, len(SERVICE), SERVICE, len(ACCOUNT), ACCOUNT,
                                               ctypes.byref(length), ctypes.byref(data), ctypes.byref(item))
    core = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    core.CFRelease.argtypes = [ctypes.c_void_p]
    core.CFRelease.restype = None
    try:
        if result not in (0, -25300):
            raise RuntimeError(f'Keychain access failed ({result}). Allow access or unlock the login Keychain.')
        if value is None:
            if result == -25300:
                raise RuntimeError('Save the API key in the GUI first.')
            return ctypes.string_at(data, length.value).decode('utf-8')
        password = value.strip().encode('utf-8')
        if not password:
            raise ValueError('API key is empty.')
        if result == 0:
            status = api.SecKeychainItemModifyAttributesAndData(item, None, len(password), password)
        else:
            status = api.SecKeychainAddGenericPassword(None, len(SERVICE), SERVICE, len(ACCOUNT), ACCOUNT,
                                                      len(password), password, None)
        if status:
            raise RuntimeError(f'Cannot save API key to Keychain ({status}).')
    finally:
        if data.value:
            api.SecKeychainItemFreeContent(None, data)
        if item.value:
            core.CFRelease(item)
