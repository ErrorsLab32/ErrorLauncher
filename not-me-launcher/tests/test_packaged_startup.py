from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import main


class PackagedStartupTests(unittest.TestCase):
    def test_temp_copy_delegates_to_installed_launcher(self):
        stable = Path("C:/Users/Player/AppData/Local/Programs/ErrorLabs Playtest/ErrorLabsPlaytest.exe")
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(Path(tempfile.gettempdir()) / "ErrorLabsPlaytest.exe")), \
             patch.object(sys, "argv", ["ErrorLabsPlaytest.exe", "--background"]), \
             patch.object(main, "_write_startup_diagnostics"), \
             patch.object(main, "installed_launcher_path", return_value=stable), \
             patch.object(main, "is_forbidden_launcher_path", return_value=False), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(main.subprocess, "Popen") as launch:
            self.assertEqual(main.main(), 0)
        self.assertEqual(launch.call_args.args[0], [str(stable), "--background"])
        self.assertEqual(launch.call_args.kwargs["cwd"], str(stable.parent))
        self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_uninstalled_temp_copy_fails_without_starting_app(self):
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(Path(tempfile.gettempdir()) / "ErrorLabsPlaytest.exe")), \
             patch.object(main, "_write_startup_diagnostics"), \
             patch.object(main, "_write_startup_crash") as crash, \
             patch.object(main, "is_forbidden_launcher_path", return_value=False), \
             patch.object(Path, "is_file", return_value=False), \
             patch.object(main.subprocess, "Popen") as launch:
            self.assertEqual(main.main(), 1)
        crash.assert_called_once()
        launch.assert_not_called()
