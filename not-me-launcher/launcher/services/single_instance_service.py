from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstanceService(QObject):
    activation_requested = Signal()

    def __init__(self, data_path: Path) -> None:
        super().__init__()
        self._name = "ErrorLabsPlaytest-" + str(abs(hash(str(data_path))))
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        server = QLocalServer(self)
        if server.listen(self._name):
            server.newConnection.connect(self._on_connection)
            self._server = server
            return True
        socket = QLocalSocket(self)
        socket.connectToServer(self._name)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self._name)
        if server.listen(self._name):
            server.newConnection.connect(self._on_connection)
            self._server = server
            return True
        return False

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self._name)
            self._server = None

    def _on_connection(self) -> None:
        socket = self._server.nextPendingConnection() if self._server else None
        if socket is not None:
            self.activation_requested.emit()
            socket.disconnectFromServer()
