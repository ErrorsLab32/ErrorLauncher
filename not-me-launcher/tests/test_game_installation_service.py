from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from launcher.installation_preferences import (
    InstallationPathError,
    InstallationPreferences,
)
from launcher.models.release_info import ReleaseAsset, ReleaseInfo
from launcher.services.game_installation_service import (
    GameInstallationError,
    GameInstallationService,
)


class GameInstallationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-installation-output"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.preferences = InstallationPreferences(
            self.root / "app-data" / "installation.json",
            self.root / "legacy.json",
        )
        self.install_path = self.preferences.validate_and_set_install_path(
            self.root / "Install"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_detects_actual_split_7z_first_volume(self) -> None:
        files = [
            Path("Windows.7z.003"),
            Path("Windows.7z.001"),
            Path("Windows.7z.002"),
        ]
        self.assertEqual(
            GameInstallationService.detect_first_volume(files),
            Path("Windows.7z.001"),
        )

    def test_unknown_archive_names_are_reported(self) -> None:
        with self.assertRaisesRegex(
            GameInstallationError,
            "unknown.bin",
        ):
            GameInstallationService.detect_first_volume([Path("unknown.bin")])

    def test_complete_download_is_detected_by_release_sizes(self) -> None:
        release = self._release("v0.6.2")
        directory = self.preferences.release_download_directory(release.tag_name)
        directory.mkdir(parents=True)
        (directory / "Windows.7z.001").write_bytes(b"first")
        (directory / "Windows.7z.002").write_bytes(b"second")

        service = GameInstallationService(self.preferences)

        self.assertTrue(service.download_is_complete(release))
        (directory / "Windows.7z.002").write_bytes(b"bad")
        self.assertFalse(service.download_is_complete(release))

    def test_install_uses_staging_saves_metadata_and_cleans_archives(self) -> None:
        release = self._release("v0.6.2")
        directory = self._write_downloads(release)
        service = GameInstallationService(self.preferences)

        def fake_extract(_extractor: Path, _volume: Path, staging: Path) -> None:
            build = staging / "NotMeBuild"
            build.mkdir()
            (build / "NotMe.exe").write_bytes(b"new game")

        with patch.object(service, "find_extractor", return_value=Path("7z.exe")):
            with patch.object(service, "_extract", side_effect=fake_extract):
                result = service.install(release, lambda _stage: None)

        self.assertEqual(result.executable_path, Path("game") / "NotMe.exe")
        self.assertEqual((self.install_path / result.executable_path).read_bytes(), b"new game")
        self.assertEqual(self.preferences.installed_version, "v0.6.2")
        self.assertTrue(self.preferences.installation_is_valid)
        self.assertFalse((directory / "Windows.7z.001").exists())
        self.assertFalse((directory / "Windows.7z.002").exists())

    def test_metadata_failure_rolls_back_working_game(self) -> None:
        old_executable = self.install_path / "game" / "NotMe.exe"
        old_executable.parent.mkdir(parents=True)
        old_executable.write_bytes(b"old game")
        self.preferences.mark_installation_complete(
            "v0.5.0", Path("game") / "NotMe.exe"
        )
        release = self._release("v0.6.2")
        self._write_downloads(release)
        service = GameInstallationService(self.preferences)

        def fake_extract(_extractor: Path, _volume: Path, staging: Path) -> None:
            (staging / "NotMe.exe").write_bytes(b"new game")

        with patch.object(service, "find_extractor", return_value=Path("7z.exe")):
            with patch.object(service, "_extract", side_effect=fake_extract):
                with patch.object(
                    self.preferences,
                    "mark_installation_complete",
                    side_effect=InstallationPathError("metadata failure"),
                ):
                    with self.assertRaisesRegex(
                        GameInstallationError,
                        "Не удалось заменить",
                    ):
                        service.install(release, lambda _stage: None)

        self.assertEqual(old_executable.read_bytes(), b"old game")
        self.assertEqual(self.preferences.installed_version, "v0.5.0")

    def test_failure_before_old_game_move_does_not_delete_it(self) -> None:
        old_executable = self.install_path / "game" / "NotMe.exe"
        old_executable.parent.mkdir(parents=True)
        old_executable.write_bytes(b"old game")
        self.preferences.mark_installation_complete(
            "v0.5.0", Path("game") / "NotMe.exe"
        )
        release = self._release("v0.6.2")
        self._write_downloads(release)
        service = GameInstallationService(self.preferences)

        def fake_extract(_extractor: Path, _volume: Path, staging: Path) -> None:
            (staging / "NotMe.exe").write_bytes(b"new game")

        original_write_text = Path.write_text

        def fail_marker(path: Path, data: str, **kwargs) -> int:
            if path.name == ".replacement-version":
                raise OSError("marker denied")
            return original_write_text(path, data, **kwargs)

        with patch.object(service, "find_extractor", return_value=Path("7z.exe")):
            with patch.object(service, "_extract", side_effect=fake_extract):
                with patch.object(Path, "write_text", fail_marker):
                    with self.assertRaises(GameInstallationError):
                        service.install(release, lambda _stage: None)

        self.assertEqual(old_executable.read_bytes(), b"old game")
        self.assertEqual(self.preferences.installed_version, "v0.5.0")

    def _write_downloads(self, release: ReleaseInfo) -> Path:
        directory = self.preferences.release_download_directory(release.tag_name)
        directory.mkdir(parents=True)
        (directory / "Windows.7z.001").write_bytes(b"first")
        (directory / "Windows.7z.002").write_bytes(b"second")
        return directory

    @staticmethod
    def _release(tag: str) -> ReleaseInfo:
        return ReleaseInfo(
            tag_name=tag,
            name="Build",
            body="",
            published_at="",
            assets=(
                ReleaseAsset(1, "Windows.7z.001", 5, "", "https://example/1"),
                ReleaseAsset(2, "Windows.7z.002", 6, "", "https://example/2"),
                ReleaseAsset(3, "7z2602.exe", 100, "", "https://example/3"),
            ),
            http_status=200,
        )


if __name__ == "__main__":
    unittest.main()
