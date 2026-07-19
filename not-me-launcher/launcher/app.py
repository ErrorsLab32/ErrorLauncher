from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QCoreApplication, QLockFile, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget

from launcher.config import load_launcher_update_config
from launcher.launcher_update_controller import LauncherUpdateController
from launcher.navigation import NavigationController
from launcher.installation_preferences import InstallationPreferences
from launcher.version import LAUNCHER_VERSION
from launcher.views.launcher_view import LauncherView
from launcher.views.launcher_update_view import LauncherUpdateView
from launcher.views.login_view import LoginView
from launcher.views.recovery_view import RecoveryView
from launcher.views.register_view import RegisterView
from launcher.views.settings_view import SettingsView


class LauncherWindow(QMainWindow):
    """Main window containing all launcher screens."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ErrorLabs Playtest")
        self.resize(1100, 680)
        self.setMinimumSize(900, 560)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.navigation = NavigationController(self.stack)
        self.installation_preferences = InstallationPreferences()
        self._closing_for_update = False
        self._view_before_update = None

        self.login_view = LoginView()
        self.register_view = RegisterView()
        self.recovery_view = RecoveryView()
        self.launcher_view = LauncherView(self.installation_preferences)
        self.launcher_view.set_game_operations_blocked(True)
        self.launcher_update_view = LauncherUpdateView()
        self.settings_view = SettingsView(self.installation_preferences)

        self.navigation.add_view("login", self.login_view)
        self.navigation.add_view("register", self.register_view)
        self.navigation.add_view("recovery", self.recovery_view)
        self.navigation.add_view("launcher", self.launcher_view)
        self.navigation.add_view("launcher_update", self.launcher_update_view)
        self.navigation.add_view("settings", self.settings_view)

        self.launcher_update_controller = LauncherUpdateController(
            load_launcher_update_config(),
            self.installation_preferences,
            self.launcher_view,
            self.launcher_update_view,
        )

        self._connect_navigation()
        self._connect_launcher_update()
        self.navigation.show("login")

    def start_background_services(self) -> None:
        self.launcher_update_controller.start()

    def _connect_navigation(self) -> None:
        self.login_view.login_requested.connect(
            lambda: self.navigation.show("launcher")
        )
        self.login_view.register_requested.connect(
            lambda: self.navigation.show("register")
        )
        self.login_view.recovery_requested.connect(
            lambda: self.navigation.show("recovery")
        )
        self.register_view.back_requested.connect(
            lambda: self.navigation.show("login")
        )
        self.register_view.registration_requested.connect(
            lambda: self.navigation.show("login")
        )
        self.recovery_view.back_requested.connect(
            lambda: self.navigation.show("login")
        )
        self.recovery_view.password_change_requested.connect(
            lambda: self.navigation.show("login")
        )
        self.launcher_view.settings_requested.connect(
            lambda: self.navigation.show("settings")
        )
        self.settings_view.back_requested.connect(
            lambda: self.navigation.show("launcher")
        )
        self.settings_view.logout_requested.connect(
            lambda: self.navigation.show("login")
        )

    def _connect_launcher_update(self) -> None:
        controller = self.launcher_update_controller
        controller.initial_check_finished.connect(
            self.launcher_view.start_game_release_check
        )
        controller.show_update_view_requested.connect(self._show_launcher_update)
        controller.restore_previous_view_requested.connect(
            self._restore_view_after_update
        )
        controller.close_for_update_requested.connect(self._close_for_update)
        controller.error_requested.connect(self._show_launcher_update_error)

    def _show_launcher_update(self) -> None:
        if self.stack.currentWidget() is not self.launcher_update_view:
            self._view_before_update = self.stack.currentWidget()
        self.navigation.show("launcher_update")

    def _restore_view_after_update(self) -> None:
        if self._view_before_update is not None:
            self.stack.setCurrentWidget(self._view_before_update)
        self._view_before_update = None

    def _close_for_update(self) -> None:
        self._closing_for_update = True
        QTimer.singleShot(0, self.close)

    def _show_launcher_update_error(self, message: str) -> None:
        QMessageBox.warning(self, "ErrorLabs Playtest", message)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._closing_for_update:
            event.accept()
            return
        if self.launcher_update_controller.is_critical:
            event.ignore()
            return
        update_ready = self.launcher_update_controller.request_shutdown()
        game_ready = self.launcher_view.request_worker_shutdown()
        if update_ready and game_ready:
            event.accept()
            return
        event.ignore()
        QTimer.singleShot(200, self.close)


def load_stylesheet() -> str:
    stylesheet_path = Path(__file__).parent / "resources" / "styles.qss"
    return stylesheet_path.read_text(encoding="utf-8")


def run() -> int:
    QCoreApplication.setOrganizationName("ErrorLabs")
    QCoreApplication.setApplicationName("ErrorLabs Playtest")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())

    try:
        local_data_path = launcher_local_data_path()
    except Exception:
        return 1
    local_data_path.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(local_data_path / "errorlabs-playtest.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(100):
        return 0
    app.instance_lock = instance_lock  # type: ignore[attr-defined]

    window = LauncherWindow()
    window.show()
    _write_health_marker(local_data_path)
    _cleanup_confirmed_backup(local_data_path)
    QTimer.singleShot(0, window.start_background_services)
    return app.exec()


def _write_health_marker(local_data_path: Path) -> None:
    marker = local_data_path / "update-health" / f"{LAUNCHER_VERSION}.ok"
    temporary = marker.with_suffix(".tmp")
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text("ok\n", encoding="utf-8")
        temporary.replace(marker)
    except OSError:
        temporary.unlink(missing_ok=True)


def _cleanup_confirmed_backup(local_data_path: Path) -> None:
    if not getattr(sys, "frozen", False):
        return
    marker = local_data_path / "update-health" / f"{LAUNCHER_VERSION}.ok"
    backup = (
        Path(sys.executable).resolve().parent.parent
        / ".errorlabs-updater"
        / f"backup-{LAUNCHER_VERSION}"
    )
    if marker.is_file() and backup.is_dir():
        try:
            shutil.rmtree(backup)
        except OSError:
            pass
