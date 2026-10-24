from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from launcher.runtime_paths import is_forbidden_launcher_path


class RuntimePathTests(unittest.TestCase):
    def test_temp_and_mei_paths_are_forbidden(self) -> None:
        temp = Path(tempfile.gettempdir()).resolve()
        with patch("launcher.runtime_paths.updater_staging_root", return_value=Path("C:/stable/.errorlabs-updater")):
            self.assertTrue(is_forbidden_launcher_path(temp / "ErrorLabsPlaytest.exe"))
            self.assertTrue(is_forbidden_launcher_path(Path("C:/Users/Test/AppData/Local/Temp/_MEI123/ErrorLabsPlaytest.exe")))

    def test_stable_install_path_is_not_forbidden(self) -> None:
        with patch("launcher.runtime_paths.updater_staging_root", return_value=Path("C:/stable/.errorlabs-updater")):
            self.assertFalse(is_forbidden_launcher_path(Path("C:/Users/Test/AppData/Local/Programs/ErrorLabs Playtest/ErrorLabsPlaytest.exe")))

    def test_updater_staging_is_forbidden(self) -> None:
        with patch("launcher.runtime_paths.updater_staging_root", return_value=Path("C:/stable/.errorlabs-updater")):
            self.assertTrue(is_forbidden_launcher_path(Path("C:/stable/.errorlabs-updater/staging-0.2.9/ErrorLabsPlaytest.exe")))


if __name__ == "__main__":
    unittest.main()
