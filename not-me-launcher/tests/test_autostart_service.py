from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from launcher.services.autostart_service import AutostartService


class AutostartServiceTests(unittest.TestCase):
    def test_development_command_quotes_paths(self) -> None:
        with patch.object(sys, "frozen", False, create=True), patch.object(sys, "executable", "C:/Python Space/python.exe"):
            command = AutostartService.command(Path("C:/Source Space/main.py"))
        self.assertIn('"C:\\Python Space\\python.exe"', command)
        self.assertIn('"C:\\Source Space\\main.py"', command)
        self.assertTrue(command.endswith(" --background"))

    def test_packaged_command_uses_executable(self) -> None:
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", "C:/App Space/launcher.exe"):
            command = AutostartService.command()
        self.assertEqual(command, '"C:\\App Space\\launcher.exe" --background')

    def test_registry_failure_is_returned(self) -> None:
        service = AutostartService()
        with patch("launcher.services.autostart_service.os.name", "nt"), patch.dict(sys.modules, {"winreg": None}):
            self.assertIsNotNone(service.apply(True))


if __name__ == "__main__":
    unittest.main()
