from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, QThread, QTimer, Signal, Slot

from launcher.config import LauncherUpdateConfig
from launcher.installation_preferences import InstallationPreferences
from launcher.models.launcher_update import (
    LauncherUpdateProgress,
    LauncherUpdateRelease,
    LauncherUpdateState,
)
from launcher.services.launcher_update_service import (
    LauncherUpdateService,
    launcher_local_data_path,
)
from launcher.version import LAUNCHER_VERSION
from launcher.views.launcher_update_view import LauncherUpdateView
from launcher.views.launcher_view import LauncherView
from launcher.workers.launcher_update_check_worker import LauncherUpdateCheckWorker
from launcher.workers.launcher_update_download_worker import (
    LauncherUpdateDownloadWorker,
)


class LauncherUpdateFailureStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, version: str, count: int) -> None:
        payload = {
            "failed_update_version": version,
            "failed_update_count": count,
            "last_failure_time": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        }
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                json.dump(payload, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
                temporary_path = Path(output.name)
            os.replace(temporary_path, self.path)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


class LauncherUpdateController(QObject):
    initial_check_finished = Signal()
    show_update_view_requested = Signal()
    restore_previous_view_requested = Signal()
    close_for_update_requested = Signal()
    error_requested = Signal(str)
    state_changed = Signal(object)

    def __init__(
        self,
        config: LauncherUpdateConfig,
        preferences: InstallationPreferences,
        launcher_view: LauncherView,
        update_view: LauncherUpdateView,
        service: LauncherUpdateService | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.preferences = preferences
        self.launcher_view = launcher_view
        self.update_view = update_view
        self.service = service or LauncherUpdateService(config.repository)
        self.state = LauncherUpdateState.Idle
        self.pending_release: LauncherUpdateRelease | None = None
        self._check_thread: QThread | None = None
        self._check_worker: LauncherUpdateCheckWorker | None = None
        self._download_thread: QThread | None = None
        self._download_worker: LauncherUpdateDownloadWorker | None = None
        self._downloaded_package: Path | None = None
        self._initial_check_finished = False
        self._failure_counts: dict[str, int] = {}
        self._failure_store = LauncherUpdateFailureStore(
            launcher_local_data_path() / "launcher-update-state.json"
        )
        self.timer = QTimer(self)
        self.timer.setInterval(config.check_interval_ms)
        self.timer.timeout.connect(self.check_now)
        preferences.download_active_changed.connect(self._on_game_busy_changed)

    def start(self) -> None:
        self.timer.start()
        self.check_now()

    @Slot()
    def check_now(self) -> bool:
        if self._check_thread is not None or self.is_critical:
            return False
        self._set_state(LauncherUpdateState.Checking)
        thread = QThread(self)
        worker = LauncherUpdateCheckWorker(self.service, LAUNCHER_VERSION)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_check_succeeded)
        worker.failed.connect(self._on_check_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_check_thread)
        self._check_thread = thread
        self._check_worker = worker
        thread.start()
        return True

    @property
    def is_critical(self) -> bool:
        return self.state in {
            LauncherUpdateState.Downloading,
            LauncherUpdateState.Verifying,
            LauncherUpdateState.ReadyToApply,
            LauncherUpdateState.Applying,
            LauncherUpdateState.Restarting,
        }

    @Slot(object)
    def _on_check_succeeded(
        self,
        release: LauncherUpdateRelease | None,
    ) -> None:
        if release is None:
            self._set_state(LauncherUpdateState.Idle)
            self._finish_initial_check()
            return
        version = release.manifest.version
        if self._failure_counts.get(version, 0) >= 3:
            self.service.log(
                f"automatic update suppressed for this session version={version}"
            )
            self._set_state(LauncherUpdateState.Error)
            self._finish_initial_check()
            return
        self.pending_release = release
        self._set_state(LauncherUpdateState.UpdateAvailable)

        if not getattr(sys, "frozen", False) and os.getenv(
            "LAUNCHER_UPDATE_DEV_MODE", ""
        ) != "1":
            self.service.log(
                f"update available version={version}; download skipped in dev mode"
            )
            self.pending_release = None
            self._set_state(LauncherUpdateState.Idle)
            self._finish_initial_check()
            return
        if self.preferences.download_active:
            self._set_state(LauncherUpdateState.WaitingForGameOperation)
            self.launcher_view.show_pending_launcher_update(True)
            self._finish_initial_check()
            return
        self._begin_update()

    @Slot(str)
    def _on_check_failed(self, message: str) -> None:
        self.service.log(f"background check failed: {message}")
        self._set_state(LauncherUpdateState.Error)
        self._finish_initial_check()

    @Slot()
    def _clear_check_thread(self) -> None:
        self._check_thread = None
        self._check_worker = None

    def _finish_initial_check(self) -> None:
        if self._initial_check_finished:
            return
        self._initial_check_finished = True
        self.launcher_view.set_game_operations_blocked(False)
        self.initial_check_finished.emit()

    @Slot(bool)
    def _on_game_busy_changed(self, active: bool) -> None:
        if active or self.pending_release is None:
            return
        if self.state is LauncherUpdateState.WaitingForGameOperation:
            self.launcher_view.set_game_operations_blocked(True)
            self.launcher_view.show_pending_launcher_update(False)
            QTimer.singleShot(0, self._begin_update)

    def _begin_update(self) -> None:
        release = self.pending_release
        if release is None or self._download_thread is not None:
            return
        if self.preferences.download_active:
            self._set_state(LauncherUpdateState.WaitingForGameOperation)
            self.launcher_view.show_pending_launcher_update(True)
            return
        self.launcher_view.set_game_operations_blocked(True)
        self.launcher_view.show_pending_launcher_update(False)
        self.show_update_view_requested.emit()
        self.update_view.show_download_progress(0, 0, release.package.size)
        self._set_state(LauncherUpdateState.Downloading)

        thread = QThread(self)
        worker = LauncherUpdateDownloadWorker(self.service, release)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_download_progress)
        worker.succeeded.connect(self._on_download_succeeded)
        worker.failed.connect(self._on_download_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_download_thread)
        self._download_thread = thread
        self._download_worker = worker
        thread.start()

    @Slot(object)
    def _on_download_progress(self, progress: LauncherUpdateProgress) -> None:
        self.update_view.show_download_progress(
            progress.percent,
            progress.downloaded_bytes,
            progress.total_bytes,
        )

    @Slot(str)
    def _on_download_succeeded(self, package_path: str) -> None:
        self._set_state(LauncherUpdateState.Verifying)
        self.update_view.show_preparing()
        self._downloaded_package = Path(package_path)

    @Slot(str)
    def _on_download_failed(self, message: str) -> None:
        self._record_failure(message)
        self._restore_after_error(message)

    @Slot()
    def _clear_download_thread(self) -> None:
        self._download_thread = None
        self._download_worker = None
        package = self._downloaded_package
        self._downloaded_package = None
        if package is not None:
            QTimer.singleShot(0, lambda: self._apply_update(package))

    def _apply_update(self, package_path: Path) -> None:
        release = self.pending_release
        if release is None:
            self._restore_after_error("Описание обновления лаунчера потеряно.")
            return
        self._set_state(LauncherUpdateState.ReadyToApply)
        if not getattr(sys, "frozen", False):
            self.service.log(
                f"application step skipped in dev mode version={release.manifest.version}"
            )
            self.pending_release = None
            self._set_state(LauncherUpdateState.Idle)
            self.restore_previous_view_requested.emit()
            self.launcher_view.set_game_operations_blocked(False)
            self._finish_initial_check()
            return

        self._set_state(LauncherUpdateState.Applying)
        source_updater = Path(sys.executable).resolve().parent / "ErrorLabsUpdater.exe"
        if not source_updater.is_file():
            self._record_failure("updater executable missing")
            self._restore_after_error("Не найден компонент установки обновления.")
            return
        runtime_directory = (
            launcher_local_data_path()
            / "updater-runtime"
            / release.manifest.version
        )
        runtime_directory.mkdir(parents=True, exist_ok=True)
        runtime_updater = runtime_directory / "ErrorLabsUpdater.exe"
        try:
            shutil.copy2(source_updater, runtime_updater)
        except OSError:
            self._record_failure("updater copy failed")
            self._restore_after_error("Не удалось подготовить установщик обновления.")
            return
        arguments = [
            "--package",
            str(package_path.resolve()),
            "--target",
            str(Path(sys.executable).resolve().parent),
            "--entrypoint",
            str(release.manifest.entrypoint),
            "--pid",
            str(os.getpid()),
            "--version",
            release.manifest.version,
        ]
        try:
            started, _process_id = QProcess.startDetached(
                str(runtime_updater),
                arguments,
                str(runtime_directory),
            )
        except (OSError, TypeError):
            started = False
        if not started:
            self._record_failure("updater process start failed")
            self._restore_after_error("Не удалось запустить установщик обновления.")
            return
        self._set_state(LauncherUpdateState.Restarting)
        self.update_view.show_restarting()
        self.close_for_update_requested.emit()

    def _record_failure(self, diagnostic: str) -> None:
        release = self.pending_release
        version = release.manifest.version if release else "unknown"
        count = self._failure_counts.get(version, 0) + 1
        self._failure_counts[version] = count
        self._failure_store.record(version, count)
        self.service.log(
            f"update attempt failed version={version} count={count}: {diagnostic}"
        )

    def _restore_after_error(self, message: str) -> None:
        self.pending_release = None
        self._set_state(LauncherUpdateState.Error)
        self.restore_previous_view_requested.emit()
        self.launcher_view.set_game_operations_blocked(False)
        self._finish_initial_check()
        self.error_requested.emit(message)

    def request_shutdown(self) -> bool:
        self.timer.stop()
        threads = (self._check_thread, self._download_thread)
        return not any(thread is not None and thread.isRunning() for thread in threads)

    def _set_state(self, state: LauncherUpdateState) -> None:
        self.state = state
        self.state_changed.emit(state)
