from PySide6.QtCore import QObject, Signal, Slot

from launcher.services.launcher_update_service import (
    LauncherUpdateError,
    LauncherUpdateService,
)


class LauncherUpdateCheckWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        service: LauncherUpdateService,
        current_version: str,
    ) -> None:
        super().__init__()
        self._service = service
        self._current_version = current_version

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(
                self._service.check_for_update(self._current_version)
            )
        except LauncherUpdateError as error:
            self.failed.emit(error.user_message)
        finally:
            self.finished.emit()
