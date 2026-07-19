from PySide6.QtCore import QObject, Signal, Slot

from launcher.installation_preferences import InstallationPreferences
from launcher.models.release_info import ReleaseInfo
from launcher.services.game_installation_service import (
    GameInstallationError,
    GameInstallationService,
)


class InstallationWorker(QObject):
    stage_changed = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        preferences: InstallationPreferences,
        release: ReleaseInfo,
    ) -> None:
        super().__init__()
        self._preferences = preferences
        self._release = release

    @Slot()
    def run(self) -> None:
        try:
            result = GameInstallationService(self._preferences).install(
                self._release,
                self.stage_changed.emit,
            )
            self.succeeded.emit(result)
        except GameInstallationError as error:
            self.failed.emit(error.user_message)
        except Exception:
            self.failed.emit("Не удалось установить сборку.")
        finally:
            self.finished.emit()
