from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayService(QObject):
    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject, icon: QIcon | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon or QIcon(), self)
        self._tray.setToolTip("Not Me Launcher")
        menu = QMenu()
        open_action = QAction("Открыть", menu)
        quit_action = QAction("Выйти", menu)
        open_action.triggered.connect(self.open_requested)
        quit_action.triggered.connect(self.quit_requested)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._activated)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_requested.emit()
