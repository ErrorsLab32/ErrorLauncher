from PySide6.QtCore import QObject, Signal, Slot
from collections.abc import Callable
import threading
from pathlib import Path

from launcher.config import GitHubConfig
from launcher.models.release_info import ReleaseInfo
from launcher.services.github_release_service import GitHubReleaseError, GitHubReleaseService


class DownloadWorker(QObject):
    progress = Signal(object)
    succeeded = Signal(str)
    failed = Signal(str)
    access_code_invalid = Signal()
    finished = Signal()

    def __init__(
        self,
        config: GitHubConfig,
        release: ReleaseInfo,
        destination_directory: Path,
        forget_invalid_token: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._release = release
        self._destination_directory = destination_directory.expanduser().resolve()
        self._cancel_event = threading.Event()
        self._forget_invalid_token = forget_invalid_token

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            directory = GitHubReleaseService(self._config).download_archive_parts(
                self._release,
                self._destination_directory,
                self.progress.emit,
                self._cancel_event.is_set,
            )
            self.succeeded.emit(str(directory))
        except GitHubReleaseError as error:
            if error.status_code in (401, 403) and self._forget_invalid_token is not None:
                self._forget_invalid_token()
                self.access_code_invalid.emit()
            self.failed.emit(error.user_message)
        finally:
            self.finished.emit()
