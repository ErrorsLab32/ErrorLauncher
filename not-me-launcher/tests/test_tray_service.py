import unittest
from unittest.mock import MagicMock, patch

from launcher.services.tray_service import TrayService


class TrayServiceTests(unittest.TestCase):
    def test_keeps_tray_menu_and_actions_alive_and_connects_actions(self) -> None:
        with patch("launcher.services.tray_service.QSystemTrayIcon", MagicMock()), \
             patch("launcher.services.tray_service.QMenu", MagicMock()), \
             patch("launcher.services.tray_service.QAction", MagicMock()):
            tray = TrayService(None, MagicMock())
            self.assertIsNotNone(tray.tray_icon)
            self.assertIsNotNone(tray.tray_menu)
            self.assertIsNotNone(tray.tray_open_action)
            self.assertIsNotNone(tray.tray_exit_action)

    def test_show_delegates_to_tray_icon(self) -> None:
        with patch("launcher.services.tray_service.QSystemTrayIcon", MagicMock()) as icon, \
             patch("launcher.services.tray_service.QMenu", MagicMock()), \
             patch("launcher.services.tray_service.QAction", MagicMock()):
            tray = TrayService(None, MagicMock())
            tray.show()
            icon.return_value.show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
