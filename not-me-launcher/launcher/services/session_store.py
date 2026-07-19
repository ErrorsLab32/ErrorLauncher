import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Callable


class SessionStoreError(RuntimeError):
    """The protected local session could not be read or written."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


class DpapiSessionStore:
    """Stores a bearer token encrypted for the current Windows user only."""

    def __init__(
        self,
        path: Path,
        protect: Callable[[bytes], bytes] | None = None,
        unprotect: Callable[[bytes], bytes] | None = None,
    ) -> None:
        self.path = path
        self._protect = protect or _protect_for_current_user
        self._unprotect = unprotect or _unprotect_for_current_user

    def load(self) -> str | None:
        if not self.path.is_file():
            return None
        try:
            token = self._unprotect(self.path.read_bytes()).decode("utf-8")
            if not token:
                raise ValueError("empty token")
            return token
        except (OSError, UnicodeError, ValueError, SessionStoreError):
            self.clear()
            return None

    def save(self, token: str) -> None:
        try:
            encrypted = self._protect(token.encode("utf-8"))
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(encrypted)
            temporary.replace(self.path)
        except (OSError, UnicodeError, SessionStoreError) as error:
            raise SessionStoreError("Не удалось сохранить защищённую сессию.") from error

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def _protect_for_current_user(value: bytes) -> bytes:
    return _crypt(value, "CryptProtectData")


def _unprotect_for_current_user(value: bytes) -> bytes:
    return _crypt(value, "CryptUnprotectData")


def _crypt(value: bytes, function_name: str) -> bytes:
    if not value:
        raise SessionStoreError("Empty DPAPI input")
    try:
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError as error:
        raise SessionStoreError("Windows DPAPI is unavailable.") from error

    source_buffer = (ctypes.c_byte * len(value)).from_buffer_copy(value)
    source = _DataBlob(len(value), source_buffer)
    result = _DataBlob()
    function = getattr(crypt32, function_name)
    function.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    function.restype = wintypes.BOOL
    if not function(
        ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(result)
    ):
        raise SessionStoreError("Windows DPAPI operation failed.")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)
