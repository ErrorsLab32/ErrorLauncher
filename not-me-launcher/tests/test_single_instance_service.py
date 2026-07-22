import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication

from launcher.services.single_instance_service import SingleInstanceService


class SingleInstanceServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_identity_is_stable_across_paths(self) -> None:
        with patch("launcher.services.single_instance_service.getpass.getuser", return_value="player"):
            first = SingleInstanceService()
            second = SingleInstanceService()
        self.assertEqual(first.endpoint, second.endpoint)
        self.assertEqual(first.mutex_name, second.mutex_name)
        self.assertIn("ErrorLabs.NotMeLauncher", first.endpoint)

    def test_secondary_manual_launch_sends_show_and_exits(self) -> None:
        socket = MagicMock()
        socket.waitForConnected.return_value = True
        with patch("launcher.services.single_instance_service.QLocalSocket", return_value=socket), \
             patch.object(SingleInstanceService, "_acquire_mutex", return_value=False):
            service = SingleInstanceService()
            self.assertFalse(service.acquire(background=False))
        socket.write.assert_called_once_with(b"show")

    def test_secondary_background_launch_does_not_activate_window(self) -> None:
        socket = MagicMock()
        socket.waitForConnected.return_value = True
        with patch("launcher.services.single_instance_service.QLocalSocket", return_value=socket), \
             patch.object(SingleInstanceService, "_acquire_mutex", return_value=False):
            service = SingleInstanceService()
            self.assertFalse(service.acquire(background=True))
        socket.write.assert_called_once_with(b"background")


if __name__ == "__main__":
    unittest.main()
