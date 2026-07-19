from pathlib import Path

from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from launcher.config import load_github_config
from launcher.installation_preferences import (
    InstallationPathError,
    InstallationPreferences,
    format_size,
)
from launcher.models.release_info import DownloadProgress, ReleaseInfo
from launcher.models.installation_state import InstallationState
from launcher.services.game_installation_service import (
    GameInstallationService,
    InstallationResult,
)
from launcher.services.game_process_service import GameLaunchError, GameProcessService
from launcher.workers.download_worker import DownloadWorker
from launcher.workers.installation_worker import InstallationWorker
from launcher.workers.release_check_worker import ReleaseCheckWorker


class LauncherView(QWidget):
    settings_requested = Signal()

    def __init__(self, preferences: InstallationPreferences) -> None:
        super().__init__()
        self.setObjectName("page")
        self._preferences = preferences
        self._release: ReleaseInfo | None = None
        self._release_thread: QThread | None = None
        self._release_worker: ReleaseCheckWorker | None = None
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._installation_thread: QThread | None = None
        self._installation_worker: InstallationWorker | None = None
        self._check_started = False
        self._installed_version = preferences.installed_version
        self._state = InstallationState.NotInstalled
        self._launcher_update_blocked = False

        root = QVBoxLayout(self)
        root.setContentsMargins(42, 28, 42, 34)
        root.setSpacing(0)
        root.addLayout(self._build_header())
        root.addWidget(self._separator())
        root.addSpacing(30)
        root.addLayout(self._build_game_heading())
        root.addSpacing(26)
        root.addLayout(self._build_patch_notes(), 1)
        root.addSpacing(18)
        root.addWidget(self._separator())
        root.addSpacing(14)
        root.addLayout(self._build_version_row())
        root.addSpacing(18)
        root.addLayout(self._build_action_area())
        preferences.install_path_changed.connect(self._on_install_path_changed)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        if not self._check_started:
            self.start_game_release_check()

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 16)
        header.setSpacing(14)
        brand = QLabel("ERRORLABS PLAYTEST")
        brand.setObjectName("brandTitle")
        user = QLabel("player_demo")
        user.setObjectName("mutedLabel")
        settings_button = QPushButton("НАСТРОЙКИ")
        settings_button.setObjectName("headerButton")
        settings_button.clicked.connect(self.settings_requested)
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(user)
        header.addWidget(settings_button)
        return header

    def _build_game_heading(self) -> QHBoxLayout:
        heading = QHBoxLayout()
        heading.setSpacing(18)
        game_title = QLabel("NOT ME")
        game_title.setObjectName("gameTitle")
        build_label = QLabel("ТЕСТОВАЯ СБОРКА")
        build_label.setObjectName("buildLabel")
        heading.addWidget(game_title)
        heading.addWidget(build_label, alignment=Qt.AlignmentFlag.AlignBottom)
        heading.addStretch()
        return heading

    def _build_patch_notes(self) -> QVBoxLayout:
        section = QVBoxLayout()
        section.setSpacing(10)
        self.patch_title = QLabel("ПРОВЕРКА ПОСЛЕДНЕГО РЕЛИЗА")
        self.patch_title.setObjectName("sectionCaption")
        self.release_meta = QLabel("")
        self.release_meta.setObjectName("progressDetail")
        section.addWidget(self.patch_title)
        section.addWidget(self.release_meta)
        self.patch_notes = QTextBrowser()
        self.patch_notes.setObjectName("patchNotes")
        self.patch_notes.setFrameShape(QFrame.Shape.NoFrame)
        self.patch_notes.setReadOnly(True)
        self.patch_notes.setOpenExternalLinks(False)
        self.patch_notes.setOpenLinks(False)
        self.patch_notes.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.patch_notes.document().setDefaultStyleSheet(
            "body { color: #d7d5cf; background: transparent; "
            "font-family: 'Segoe UI'; font-size: 15px; }"
            "h1 { color: #f2f0ea; font-size: 24px; margin: 8px 0 14px 0; }"
            "h2 { color: #ece9e2; font-size: 19px; margin: 18px 0 10px 0; }"
            "p { margin: 6px 0; }"
            "li { margin: 4px 0; }"
            "blockquote { color: #9c9b95; margin-left: 14px; }"
        )
        self._set_patch_notes_markdown("Проверка обновлений…")
        section.addWidget(self.patch_notes, 1)
        return section

    def _build_version_row(self) -> QHBoxLayout:
        versions = QHBoxLayout()
        versions.setSpacing(20)
        current_caption = QLabel("УСТАНОВЛЕНО")
        current_caption.setObjectName("metaCaption")
        self.current_version = QLabel(self._installed_version or "—")
        self.current_version.setObjectName("metaValue")
        latest_caption = QLabel("ДОСТУПНО")
        latest_caption.setObjectName("metaCaption")
        self.latest_version = QLabel("—")
        self.latest_version.setObjectName("metaValue")
        self.status_label = QLabel("ПРОВЕРКА ОБНОВЛЕНИЙ")
        self.status_label.setObjectName("statusLabel")
        versions.addWidget(current_caption)
        versions.addWidget(self.current_version)
        versions.addSpacing(10)
        versions.addWidget(latest_caption)
        versions.addWidget(self.latest_version)
        versions.addStretch()
        versions.addWidget(self.status_label)
        return versions

    def _build_action_area(self) -> QHBoxLayout:
        area = QHBoxLayout()
        area.addStretch()
        action_column = QVBoxLayout()
        action_column.setSpacing(7)
        self.path_hint = QLabel("Папка установки будет выбрана перед загрузкой")
        self.path_hint.setObjectName("progressDetail")
        self.launcher_update_notice = QLabel("")
        self.launcher_update_notice.setObjectName("progressDetail")
        self.launcher_update_notice.setVisible(False)
        self.progress_label = QLabel("Проверка обновлений")
        self.progress_label.setObjectName("progressLabel")
        self.progress_detail = QLabel("")
        self.progress_detail.setObjectName("progressDetail")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.action_button = QPushButton("ПРОВЕРКА…")
        self.action_button.setObjectName("actionButton")
        self.action_button.setMinimumWidth(420)
        self.action_button.setEnabled(False)
        self.action_button.clicked.connect(self._handle_action)
        action_column.addWidget(self.path_hint)
        action_column.addWidget(self.launcher_update_notice)
        action_column.addWidget(self.progress_label)
        action_column.addWidget(self.progress_detail)
        action_column.addWidget(self.progress)
        action_column.addWidget(self.action_button)
        area.addLayout(action_column)
        self._refresh_path_hint()
        return area

    def _start_release_check(self) -> None:
        if self._release_thread is not None or self._launcher_update_blocked:
            return
        self._check_started = True
        self._set_state(InstallationState.CheckingForUpdates)

        thread = QThread(self)
        worker = ReleaseCheckWorker(load_github_config())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._on_release_loaded)
        worker.failed.connect(self._on_release_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_release_thread)
        self._release_thread = thread
        self._release_worker = worker
        thread.start()

    @Slot(object)
    def _on_release_loaded(self, release: ReleaseInfo) -> None:
        self._release = release
        self.latest_version.setText(release.tag_name)
        self.patch_title.setText(release.name.upper())
        self._set_patch_notes_markdown(
            release.body or "Описание изменений отсутствует."
        )
        published = release.published_at.replace("T", " ").replace("Z", " UTC")
        self.release_meta.setText(published)
        self.progress_label.setText(
            f"Размер загрузки: {format_size(release.total_asset_size)}"
        )
        self.progress_detail.clear()
        self.progress.setValue(0)
        self._installed_version = self._preferences.installed_version
        self.current_version.setText(self._installed_version or "—")

        installer = GameInstallationService(self._preferences)
        if (
            self._preferences.installation_recorded
            and not self._preferences.installation_is_valid
        ):
            self._show_error(
                "Установленная сборка повреждена: исполняемый файл игры не найден."
            )
        elif self._preferences.installation_is_valid:
            if self._versions_equal(release.tag_name, self._installed_version or ""):
                self._set_state(InstallationState.ReadyToPlay)
            else:
                self._set_state(InstallationState.UpdateAvailable)
        elif installer.download_is_complete(release):
            self._set_state(InstallationState.Downloaded)
        else:
            self._set_state(InstallationState.ReadyToDownload)

    @Slot(str)
    def _on_release_error(self, message: str) -> None:
        self._release = None
        self.patch_title.setText("НЕ УДАЛОСЬ ПОЛУЧИТЬ РЕЛИЗ")
        self._set_patch_notes_markdown(message)
        self._show_error(message)

    @Slot()
    def _clear_release_thread(self) -> None:
        self._release_thread = None
        self._release_worker = None

    def _start_download(self, destination_directory: Path) -> None:
        if self._release is None or self._download_thread is not None:
            return
        self._set_state(InstallationState.Downloading)

        thread = QThread(self)
        worker = DownloadWorker(
            load_github_config(),
            self._release,
            destination_directory,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_download_progress)
        worker.succeeded.connect(self._on_download_finished)
        worker.failed.connect(self._on_download_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_download_thread)
        self._download_thread = thread
        self._download_worker = worker
        self._preferences.set_download_active(True)
        thread.start()

    @Slot(object)
    def _on_download_progress(self, progress: DownloadProgress) -> None:
        self.progress.setValue(progress.percent)
        self.progress_label.setText(f"Загрузка — {progress.percent}%")
        self.progress_detail.setText(
            f"{format_size(progress.downloaded_bytes)} из "
            f"{format_size(progress.total_bytes)}"
        )

    @Slot(str)
    def _on_download_finished(self, directory: str) -> None:
        self.progress.setValue(100)
        self._set_state(InstallationState.Downloaded)
        QTimer.singleShot(0, self._start_installation)

    @Slot(str)
    def _on_download_error(self, message: str) -> None:
        self._show_error(message)

    @Slot()
    def _clear_download_thread(self) -> None:
        self._download_thread = None
        self._download_worker = None
        if self._installation_thread is None:
            self._preferences.set_download_active(False)

    def _handle_action(self) -> None:
        if self._launcher_update_blocked:
            return
        if self._state is InstallationState.ReadyToPlay:
            self._launch_game()
        elif self._state is InstallationState.Downloaded:
            self._start_installation()
        elif self._state in {
            InstallationState.ReadyToDownload,
            InstallationState.UpdateAvailable,
        }:
            self._prepare_download()
        elif self._state is InstallationState.Error and self._release is not None:
            if GameInstallationService(self._preferences).download_is_complete(
                self._release
            ):
                self._start_installation()
            else:
                self._prepare_download()
        elif self._release is None:
            self._start_release_check()

    def _start_installation(self) -> None:
        if (
            self._release is None
            or self._installation_thread is not None
            or not GameInstallationService(self._preferences).download_is_complete(
                self._release
            )
        ):
            if self._release is not None and self._installation_thread is None:
                self._show_error(
                    "Файлы сборки загружены не полностью. Повторите загрузку."
                )
            return

        self._set_state(InstallationState.Installing)
        thread = QThread(self)
        worker = InstallationWorker(self._preferences, self._release)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.stage_changed.connect(self._on_installation_stage)
        worker.succeeded.connect(self._on_installation_finished)
        worker.failed.connect(self._on_installation_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_installation_thread)
        self._installation_thread = thread
        self._installation_worker = worker
        self._preferences.set_download_active(True)
        thread.start()

    @Slot(str)
    def _on_installation_stage(self, stage: str) -> None:
        self.progress_label.setText(stage)

    @Slot(object)
    def _on_installation_finished(self, result: InstallationResult) -> None:
        self._installed_version = result.installed_version
        self.current_version.setText(result.installed_version)
        self._set_state(InstallationState.ReadyToPlay)

    @Slot(str)
    def _on_installation_error(self, message: str) -> None:
        self._show_error(message)

    @Slot()
    def _clear_installation_thread(self) -> None:
        self._installation_thread = None
        self._installation_worker = None
        if self._download_thread is None:
            self._preferences.set_download_active(False)

    def _launch_game(self) -> None:
        executable = self._preferences.installed_executable
        if executable is None:
            self._show_error(
                "Не удалось запустить игру. Файл игры отсутствует или недоступен."
            )
            return
        try:
            process_id = GameProcessService.launch(executable)
            print(f"Игра запущена, PID: {process_id}")
        except GameLaunchError as error:
            self._show_error(str(error))
            QMessageBox.warning(self, "ErrorLabs Playtest", str(error))

    def _prepare_download(self) -> None:
        if self._release is None:
            return
        if self._preferences.install_path is None and not self._choose_install_path():
            return
        try:
            self._preferences.ensure_free_space(self._release.total_asset_size)
            destination = self._preferences.release_download_directory(
                self._release.tag_name
            )
        except InstallationPathError as error:
            QMessageBox.warning(self, "ErrorLabs Playtest", str(error))
            return
        self._start_download(destination)

    def _choose_install_path(self) -> bool:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку установки Not Me",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return False
        try:
            self._preferences.validate_and_set_install_path(Path(selected))
        except InstallationPathError as error:
            QMessageBox.warning(self, "ErrorLabs Playtest", str(error))
            return False
        return True

    @Slot(object)
    def _on_install_path_changed(self, _path: object) -> None:
        self._refresh_path_hint()

    def _refresh_path_hint(self) -> None:
        self.path_hint.setVisible(self._preferences.install_path is None)

    def request_worker_shutdown(self) -> bool:
        if self._download_worker is not None:
            self._download_worker.cancel()
        running_threads = (
            thread
            for thread in (
                self._release_thread,
                self._download_thread,
                self._installation_thread,
            )
            if thread is not None and thread.isRunning()
        )
        return not any(True for _thread in running_threads)

    def start_game_release_check(self) -> None:
        if not self._check_started and not self._launcher_update_blocked:
            self._start_release_check()

    def set_game_operations_blocked(self, blocked: bool) -> None:
        self._launcher_update_blocked = blocked
        if blocked:
            self.action_button.setEnabled(False)
        else:
            self._set_state(self._state)

    def show_pending_launcher_update(self, visible: bool) -> None:
        self.launcher_update_notice.setText(
            "Обновление лаунчера будет установлено после завершения текущей операции"
            if visible
            else ""
        )
        self.launcher_update_notice.setVisible(visible)

    def _set_patch_notes_markdown(self, markdown: str) -> None:
        features = (
            QTextDocument.MarkdownFeature.MarkdownDialectGitHub
            | QTextDocument.MarkdownFeature.MarkdownNoHTML
        )
        self.patch_notes.document().setMarkdown(markdown, features)
        self.patch_notes.verticalScrollBar().setValue(0)

    def _set_state(self, state: InstallationState) -> None:
        self._state = state
        self.progress.setRange(0, 100)
        if state is InstallationState.CheckingForUpdates:
            self.status_label.setText("ПРОВЕРКА ОБНОВЛЕНИЙ")
            self.progress_label.setText("Проверка обновлений")
            self.progress_detail.clear()
            self.progress.setValue(0)
            self.action_button.setText("ПРОВЕРКА…")
            self.action_button.setEnabled(False)
        elif state is InstallationState.ReadyToDownload:
            self.status_label.setText("СБОРКА ДОСТУПНА")
            self.progress_label.setText(self._download_size_text())
            self.progress_detail.clear()
            self.progress.setValue(0)
            self.action_button.setText("СКАЧАТЬ")
            self.action_button.setEnabled(True)
        elif state is InstallationState.Downloading:
            self.status_label.setText("ЗАГРУЗКА")
            self.progress_label.setText("Загрузка — 0%")
            self.progress_detail.setText(f"0 Б из {self._download_total_text()}")
            self.progress.setValue(0)
            self.action_button.setText("ЗАГРУЗКА…")
            self.action_button.setEnabled(False)
        elif state is InstallationState.Downloaded:
            self.status_label.setText("ФАЙЛЫ СБОРКИ ЗАГРУЖЕНЫ")
            self.progress_label.setText("Файлы сборки загружены")
            self.progress_detail.clear()
            self.progress.setValue(100)
            self.action_button.setText("УСТАНОВИТЬ")
            self.action_button.setEnabled(True)
        elif state is InstallationState.Installing:
            self.status_label.setText("УСТАНОВКА")
            self.progress_label.setText("Установка сборки")
            self.progress_detail.clear()
            self.progress.setRange(0, 0)
            self.action_button.setText("УСТАНОВКА…")
            self.action_button.setEnabled(False)
        elif state is InstallationState.ReadyToPlay:
            self.status_label.setText("ГОТОВО К ЗАПУСКУ")
            self.progress_label.setText("Игра готова к запуску")
            self.progress_detail.clear()
            self.progress.setValue(100)
            self.action_button.setText("ИГРАТЬ")
            self.action_button.setEnabled(True)
        elif state is InstallationState.UpdateAvailable:
            self.status_label.setText("ДОСТУПНО ОБНОВЛЕНИЕ")
            self.progress_label.setText(self._download_size_text())
            self.progress_detail.clear()
            self.progress.setValue(0)
            self.action_button.setText("ОБНОВИТЬ")
            self.action_button.setEnabled(True)
        elif state is InstallationState.Error:
            self.status_label.setText("ОШИБКА")
            self.progress.setRange(0, 100)
            self.action_button.setText("ПОВТОРИТЬ")
            self.action_button.setEnabled(True)

    def _show_error(self, message: str) -> None:
        self._set_state(InstallationState.Error)
        self.progress_label.setText(message)
        self.progress_detail.clear()

    def _download_size_text(self) -> str:
        return (
            f"Размер загрузки: {format_size(self._release.total_asset_size)}"
            if self._release is not None
            else ""
        )

    def _download_total_text(self) -> str:
        return (
            format_size(self._release.total_archive_size)
            if self._release is not None
            else "0 Б"
        )

    @staticmethod
    def _is_newer(remote: str, installed: str) -> bool:
        try:
            return Version(LauncherView._normalized_version(remote)) > Version(
                LauncherView._normalized_version(installed)
            )
        except InvalidVersion:
            return not LauncherView._versions_equal(remote, installed)

    @staticmethod
    def _versions_equal(first: str, second: str) -> bool:
        return LauncherView._normalized_version(first) == LauncherView._normalized_version(
            second
        )

    @staticmethod
    def _normalized_version(value: str) -> str:
        normalized = value.strip().lower()
        if normalized.startswith("v"):
            normalized = normalized[1:]
        return normalized.lstrip("._-")

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        return separator
