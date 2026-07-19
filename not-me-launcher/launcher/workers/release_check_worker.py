from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from launcher.config import GitHubConfig
from launcher.services.github_release_service import GitHubReleaseError, GitHubReleaseService


class ReleaseCheckWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    access_code_invalid = Signal()
    finished = Signal()

    def __init__(self, config: GitHubConfig, forget_invalid_token: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._config = config
        self._forget_invalid_token = forget_invalid_token

    @Slot()
    def run(self) -> None:
        try:
            release = GitHubReleaseService(self._config).get_latest_release()
            self.succeeded.emit(release)
        except GitHubReleaseError as error:
            if error.status_code in (401, 403) and self._forget_invalid_token is not None:
                self._forget_invalid_token()
                self.access_code_invalid.emit()
            self.failed.emit(error.user_message)
        finally:
            self.finished.emit()
