import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from launcher.installation_preferences import (
    InstallationPathError,
    InstallationPreferences,
)


class InstallationPreferencesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-preferences-output"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.state_path = self.root / "app-data" / "installation.json"
        self.legacy_path = self.root / "legacy-installation.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_legacy_state_and_unicode_path_are_persisted(self) -> None:
        self.legacy_path.write_text(
            json.dumps({"installed_version": None}),
            encoding="utf-8",
        )
        preferences = InstallationPreferences(self.state_path, self.legacy_path)
        self.assertIsNone(preferences.install_path)

        selected = self.root / "Игры с пробелами" / "Not Me"
        normalized = preferences.validate_and_set_install_path(selected)
        reloaded = InstallationPreferences(self.state_path, self.legacy_path)

        self.assertEqual(normalized, selected.resolve())
        self.assertEqual(reloaded.install_path, selected.resolve())
        self.assertTrue(
            (selected / ".errorlabs-playtest" / "downloads").is_dir()
        )
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["installed_version"], None)
        self.assertNotIn("token", " ".join(saved.keys()).lower())

    def test_release_directory_is_inside_selected_path(self) -> None:
        preferences = InstallationPreferences(self.state_path, self.legacy_path)
        selected = preferences.validate_and_set_install_path(self.root / "Game")

        destination = preferences.release_download_directory("v/0.1.1")

        self.assertEqual(
            destination,
            selected / ".errorlabs-playtest" / "downloads" / "v_0.1.1",
        )

    def test_insufficient_space_includes_required_and_available_sizes(self) -> None:
        preferences = InstallationPreferences(self.state_path, self.legacy_path)
        preferences.validate_and_set_install_path(self.root / "Game")
        with patch(
            "launcher.installation_preferences.shutil.disk_usage",
            return_value=SimpleNamespace(free=100),
        ):
            with self.assertRaisesRegex(
                InstallationPathError,
                "Недостаточно свободного места",
            ):
                preferences.ensure_free_space(1024)

    def test_completed_installation_metadata_is_loaded_and_validated(self) -> None:
        preferences = InstallationPreferences(self.state_path, self.legacy_path)
        selected = preferences.validate_and_set_install_path(self.root / "Game")
        executable = selected / "game" / "NotMe.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"test executable")

        preferences.mark_installation_complete(
            "v0.6.2",
            Path("game") / "NotMe.exe",
        )
        reloaded = InstallationPreferences(self.state_path, self.legacy_path)

        self.assertEqual(reloaded.installed_version, "v0.6.2")
        self.assertEqual(reloaded.executable_path, Path("game") / "NotMe.exe")
        self.assertEqual(reloaded.installed_executable, executable.resolve())
        self.assertTrue(reloaded.installation_is_valid)
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["executable_path"], str(Path("game") / "NotMe.exe"))

    def test_missing_recorded_executable_is_not_a_valid_installation(self) -> None:
        selected = self.root / "Game"
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "installed_version": "v0.6.2",
                    "install_path": str(selected),
                    "executable_path": str(Path("game") / "Missing.exe"),
                }
            ),
            encoding="utf-8",
        )

        preferences = InstallationPreferences(self.state_path, self.legacy_path)

        self.assertTrue(preferences.installation_recorded)
        self.assertFalse(preferences.installation_is_valid)


if __name__ == "__main__":
    unittest.main()
