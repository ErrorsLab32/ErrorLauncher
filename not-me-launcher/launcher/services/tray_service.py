from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayService(QObject):
    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject, icon: QIcon) -> None:
        super().__init__(parent)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Not Me Launcher")
        self.tray_menu = QMenu()
        self.tray_open_action = QAction("Открыть", self.tray_menu)
        self.tray_exit_action = QAction("Выйти", self.tray_menu)
        self.tray_open_action.triggered.connect(self.open_requested)
        self.tray_exit_action.triggered.connect(self.quit_requested)
        self.tray_menu.addAction(self.tray_open_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.tray_exit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._activated)

    @property
    def is_ready(self) -> bool:
        return not self.tray_icon.icon().isNull()

    @property
    def is_visible(self) -> bool:
        return self.tray_icon.isVisible()

    def show(self) -> None:
        print(f"tray show icon_null={self.tray_icon.icon().isNull()}")
        self.tray_icon.show()
        print(f"tray visible={self.tray_icon.isVisible()}")

    def hide(self) -> None:
        self.tray_icon.hide()

    def notify(self, title: str, message: str) -> None:
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_requested.emit()
