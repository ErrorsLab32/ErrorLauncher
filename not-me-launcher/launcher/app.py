from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget, QSystemTrayIcon

from launcher.config import load_launcher_update_config
from launcher.launcher_update_controller import LauncherUpdateController
from launcher.navigation import NavigationController
from launcher.installation_preferences import InstallationPreferences
from launcher.services.launcher_update_service import launcher_local_data_path
from launcher.version import LAUNCHER_VERSION
from launcher.views.launcher_view import LauncherView
from launcher.views.launcher_update_view import LauncherUpdateView
from launcher.views.login_view import LoginView
from launcher.views.recovery_view import RecoveryView
from launcher.views.register_view import RegisterView
from launcher.views.settings_view import SettingsView
from launcher.services.autostart_service import AutostartService
from launcher.services.single_instance_service import SingleInstanceService
from launcher.services.tray_service import TrayService


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
        self._real_shutdown = False
        self.tray_service: TrayService | None = None

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

    def set_tray_service(self, tray_service: TrayService) -> None:
        self.tray_service = tray_service
        tray_service.open_requested.connect(self.restore_from_tray)
        tray_service.quit_requested.connect(self.request_real_shutdown)

    def restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def request_real_shutdown(self) -> None:
        self._real_shutdown = True
        self.close()

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
        if self._closing_for_update or self._real_shutdown:
            if self.tray_service is not None:
                self.tray_service.hide()
            event.accept()
            return
        if self.launcher_update_controller.is_critical:
            event.ignore()
            return
        tray = self.tray_service
        print(f"close-to-tray tray_ready={tray is not None and tray.is_ready} tray_visible={tray is not None and tray.is_visible}")
        if tray is None or not tray.is_ready or not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.information(self, "Not Me Launcher", "Системный трей недоступен, окно остаётся открытым.")
            event.ignore()
            return
        if not tray.is_visible:
            tray.show()
        event.ignore()
        self.hide()
        if not self.installation_preferences.tray_close_notice_shown:
            tray.notify("Not Me Launcher", "Лаунчер продолжает работать в области уведомлений")
            self.installation_preferences.mark_tray_close_notice_shown()


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
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())

    local_data_path = launcher_local_data_path()
    local_data_path.mkdir(parents=True, exist_ok=True)
    instance = SingleInstanceService(local_data_path)
    if not instance.acquire():
        return 0
    app.instance_service = instance  # type: ignore[attr-defined]

    window = LauncherWindow()
    icon_path = _launcher_icon_path()
    icon = QIcon(str(icon_path)) if icon_path is not None else app.windowIcon()
    if icon.isNull():
        icon = app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon)
    print(f"tray available={QSystemTrayIcon.isSystemTrayAvailable()} icon_path={icon_path} icon_null={icon.isNull()}")
    if not QSystemTrayIcon.isSystemTrayAvailable() or icon.isNull():
        print("tray initialization failed; main window will remain available")
        window.show()
        _write_health_marker(local_data_path)
        _cleanup_confirmed_backup(local_data_path)
        QTimer.singleShot(0, window.start_background_services)
        app.aboutToQuit.connect(instance.close)
        return app.exec()
    app.setWindowIcon(icon)
    tray = TrayService(app, icon)
    window.set_tray_service(tray)
    tray.show()
    instance.activation_requested.connect(window.restore_from_tray)
    autostart = AutostartService()
    warning = autostart.apply(window.installation_preferences.launch_on_windows_start)
    if warning:
        print(warning)
    window.installation_preferences.launch_on_windows_start_changed.connect(
        lambda enabled: _apply_autostart(autostart, enabled, tray)
    )
    if "--background" not in sys.argv:
        window.show()
    _write_health_marker(local_data_path)
    _cleanup_confirmed_backup(local_data_path)
    QTimer.singleShot(0, window.start_background_services)
    app.aboutToQuit.connect(instance.close)
    return app.exec()


def _launcher_icon_path() -> Path | None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    candidate = root / "launcher" / "resources" / "launcher.svg"
    if candidate.is_file():
        return candidate
    source_candidate = Path(__file__).resolve().parent / "resources" / "launcher.svg"
    return source_candidate if source_candidate.is_file() else None


def _apply_autostart(service: AutostartService, enabled: bool, tray: TrayService) -> None:
    warning = service.apply(enabled)
    if warning:
        print(warning)
        tray.notify("Not Me Launcher", warning)


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
