from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from launcher.navigation import NavigationController
from launcher.installation_preferences import InstallationPreferences
from launcher.views.launcher_view import LauncherView
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

        self.login_view = LoginView()
        self.register_view = RegisterView()
        self.recovery_view = RecoveryView()
        self.launcher_view = LauncherView(self.installation_preferences)
        self.settings_view = SettingsView(self.installation_preferences)

        self.navigation.add_view("login", self.login_view)
        self.navigation.add_view("register", self.register_view)
        self.navigation.add_view("recovery", self.recovery_view)
        self.navigation.add_view("launcher", self.launcher_view)
        self.navigation.add_view("settings", self.settings_view)

        self._connect_navigation()
        self.navigation.show("login")

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

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.launcher_view.request_worker_shutdown():
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

    window = LauncherWindow()
    window.show()
    return app.exec()
