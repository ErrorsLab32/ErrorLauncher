import getpass
import os
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstanceService(QObject):
    """Stable per-user mutex plus a local IPC activation channel."""

    activation_requested = Signal()
    APPLICATION_ID = "ErrorLabs.NotMeLauncher"

    def __init__(self) -> None:
        super().__init__()
        user = getpass.getuser().replace("\\", "_").replace("/", "_")
        self.endpoint = f"{self.APPLICATION_ID}.{user}"
        self.mutex_name = f"Local\\{self.APPLICATION_ID}.{user}"
        self._server: QLocalServer | None = None
        self._mutex_handle: int | None = None

    def acquire(self, background: bool = False) -> bool:
        primary = self._acquire_mutex()
        print(f"single-instance mutex={self.mutex_name} primary={primary} pid={os.getpid()}")
        if primary:
            QLocalServer.removeServer(self.endpoint)
            server = QLocalServer(self)
            if server.listen(self.endpoint):
                server.newConnection.connect(self._on_connection)
                self._server = server
                print(f"single-instance IPC listening endpoint={self.endpoint}")
                return True
            self.close()
            return False
        command = b"background" if background else b"show"
        for _attempt in range(10):
            socket = QLocalSocket(self)
            socket.connectToServer(self.endpoint)
            if socket.waitForConnected(250):
                socket.write(command)
                socket.flush()
                socket.waitForBytesWritten(250)
                socket.disconnectFromServer()
                print(f"single-instance secondary sent command={command.decode()} endpoint={self.endpoint}")
                return False
            time.sleep(0.1)
        print("single-instance secondary IPC unavailable; exiting without UI")
        return False

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self.endpoint)
            self._server = None
        if self._mutex_handle is not None and os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.ReleaseMutex(self._mutex_handle)
            ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None

    def _acquire_mutex(self) -> bool:
        if os.name != "nt":
            return True
        import ctypes
        ctypes.windll.kernel32.SetLastError(0)
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.mutex_name)
        if not handle:
            return False
        if ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.kernel32.CloseHandle(handle)
            return False
        self._mutex_handle = handle
        return True

    def _on_connection(self) -> None:
        socket = self._server.nextPendingConnection() if self._server else None
        if socket is None:
            return
        if socket.waitForReadyRead(250) and bytes(socket.readAll()) == b"show":
            print(f"single-instance activation received endpoint={self.endpoint}")
            self.activation_requested.emit()
        socket.disconnectFromServer()
