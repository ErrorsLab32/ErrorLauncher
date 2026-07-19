"""Per-user storage for the playtest access token."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


class AccessTokenStoreError(Exception):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class WindowsDpapiProtector:
    def __init__(self) -> None:
        if not hasattr(ctypes, "windll"):
            raise AccessTokenStoreError("Windows DPAPI is unavailable.")
        self._crypt32, self._kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32

    def protect(self, value: bytes) -> bytes:
        return self._crypt(value, True)

    def unprotect(self, value: bytes) -> bytes:
        return self._crypt(value, False)

    def _crypt(self, value: bytes, protect: bool) -> bytes:
        source_buffer = ctypes.create_string_buffer(value)
        source = _DataBlob(len(value), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
        result = _DataBlob()
        function = self._crypt32.CryptProtectData if protect else self._crypt32.CryptUnprotectData
        if not function(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
            raise AccessTokenStoreError("Could not protect the access code.")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            self._kernel32.LocalFree(result.pbData)


class AccessTokenStore:
    def __init__(self, path: Path, protector: object | None = None) -> None:
        self.path, self._protector = path, protector or WindowsDpapiProtector()

    def load(self) -> str | None:
        try:
            protected = self.path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise AccessTokenStoreError("Could not read the saved access code.") from error
        try:
            token = self._protector.unprotect(protected).decode("utf-8")
        except (UnicodeError, OSError, AccessTokenStoreError) as error:
            self.delete()
            raise AccessTokenStoreError("The saved access code is unavailable.") from error
        return token or None

    def save(self, token: str) -> None:
        if not token:
            raise AccessTokenStoreError("The access code is empty.")
        try:
            protected = self._protector.protect(token.encode("utf-8"))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_bytes(protected)
            temporary.replace(self.path)
        except (OSError, AccessTokenStoreError) as error:
            raise AccessTokenStoreError("Could not save the access code.") from error

    def delete(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as error:
            raise AccessTokenStoreError("Could not remove the saved access code.") from error
