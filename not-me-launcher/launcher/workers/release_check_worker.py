from PySide6.QtCore import QObject, Signal, Slot

from launcher.config import GitHubConfig
from launcher.services.github_release_service import GitHubReleaseError, GitHubReleaseService


class ReleaseCheckWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, config: GitHubConfig) -> None:
        super().__init__()
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            release = GitHubReleaseService(self._config).get_latest_release()
            self.succeeded.emit(release)
        except GitHubReleaseError as error:
            self.failed.emit(error.user_message)
        finally:
            self.finished.emit()
