"""Windows session singleton and show-window notification, without lock files."""
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path


class WindowsInstance:
    def __init__(self, root):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateMutexW.restype = wintypes.HANDLE
        self.api.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateEventW.restype = wintypes.HANDLE
        self.api.SetEvent.argtypes = [wintypes.HANDLE]
        self.api.SetEvent.restype = wintypes.BOOL
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        identity = hashlib.sha256(str(Path(root).resolve()).casefold().encode('utf-8')).hexdigest()
        name = 'Local\\LogistraPrint-' + identity
        # Create the event first so a simultaneous second launch can signal it.
        self.event = self.api.CreateEventW(None, False, False, name + '-show')
        if not self.event:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.set_last_error(0)
        self.mutex = self.api.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not self.mutex:
            self.close()
            raise ctypes.WinError(error)
        self.primary = error != 183  # ERROR_ALREADY_EXISTS

    def notify(self):
        if not self.api.SetEvent(self.event):
            raise ctypes.WinError(ctypes.get_last_error())

    def requested(self):
        result = self.api.WaitForSingleObject(self.event, 0)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    def attach(self, root, activate):
        def poll():
            if self.requested():
                activate()
            root.after(100, poll)
        root.after(100, poll)

    def close(self):
        for attribute in ('mutex', 'event'):
            handle = getattr(self, attribute, None)
            if handle:
                self.api.CloseHandle(handle)
                setattr(self, attribute, None)
