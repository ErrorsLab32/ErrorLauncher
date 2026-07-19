from pathlib import Path
import threading

from PySide6.QtCore import QObject, Signal, Slot

from launcher.models.launcher_update import LauncherUpdateRelease
from launcher.services.launcher_update_service import (
    LauncherUpdateError,
    LauncherUpdateService,
)


class LauncherUpdateDownloadWorker(QObject):
    progress = Signal(object)
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        service: LauncherUpdateService,
        release: LauncherUpdateRelease,
    ) -> None:
        super().__init__()
        self._service = service
        self._release = release
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            path = self._service.download_update(
                self._release,
                self.progress.emit,
                self._cancel_event.is_set,
            )
            self.succeeded.emit(str(path))
        except LauncherUpdateError as error:
            self.failed.emit(error.user_message)
        finally:
            self.finished.emit()
