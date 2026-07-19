import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication

from launcher.config import LauncherUpdateConfig
from launcher.installation_preferences import InstallationPreferences
from launcher.launcher_update_controller import LauncherUpdateController
from launcher.models.launcher_update import (
    LauncherUpdateAsset,
    LauncherUpdateManifest,
    LauncherUpdateRelease,
    LauncherUpdateState,
)


class FakeLauncherView:
    def __init__(self) -> None:
        self.blocked = False
        self.pending_visible = False

    def set_game_operations_blocked(self, blocked: bool) -> None:
        self.blocked = blocked

    def show_pending_launcher_update(self, visible: bool) -> None:
        self.pending_visible = visible


class FakeUpdateView:
    def show_download_progress(self, *_args) -> None:
        pass

    def show_preparing(self) -> None:
        pass

    def show_restarting(self) -> None:
        pass


class FakeService:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class LauncherUpdateControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        self.root = Path(__file__).parent / "test-controller-output"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir()
        self.preferences = InstallationPreferences(
            self.root / "app-data" / "installation.json",
            self.root / "legacy.json",
        )
        self.launcher_view = FakeLauncherView()
        self.update_view = FakeUpdateView()
        self.service = FakeService()
        patcher = patch(
            "launcher.launcher_update_controller.launcher_local_data_path",
            return_value=self.root / "local-data",
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.controller = LauncherUpdateController(
            LauncherUpdateConfig(),
            self.preferences,
            self.launcher_view,  # type: ignore[arg-type]
            self.update_view,  # type: ignore[arg-type]
            self.service,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.controller.timer.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_update_waits_for_game_operation_then_starts_automatically(self) -> None:
        self.preferences.set_download_active(True)
        with patch.object(sys, "frozen", True, create=True):
            self.controller._on_check_succeeded(self._release())

        self.assertEqual(
            self.controller.state,
            LauncherUpdateState.WaitingForGameOperation,
        )
        self.assertTrue(self.launcher_view.pending_visible)

        with patch.object(self.controller, "_begin_update") as begin_update:
            self.preferences.set_download_active(False)
            QCoreApplication.processEvents()
            begin_update.assert_called_once_with()
        self.assertTrue(self.launcher_view.blocked)

    def test_parallel_hourly_check_is_skipped(self) -> None:
        self.controller._check_thread = Mock()
        self.assertFalse(self.controller.check_now())

    def test_dev_mode_never_applies_package_to_sources(self) -> None:
        self.controller.pending_release = self._release()
        source_marker = self.root / "source-marker.txt"
        source_marker.write_text("unchanged", encoding="utf-8")
        with patch.object(sys, "frozen", False, create=True):
            with patch.dict(os.environ, {"LAUNCHER_UPDATE_DEV_MODE": "1"}):
                self.controller._apply_update(self.root / "package.zip")
        self.assertEqual(source_marker.read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(self.controller.state, LauncherUpdateState.Idle)
        self.assertTrue(any("skipped in dev mode" in value for value in self.service.messages))

    @staticmethod
    def _release() -> LauncherUpdateRelease:
        return LauncherUpdateRelease(
            "v0.2.0",
            LauncherUpdateManifest(
                "0.2.0",
                "windows-x64",
                "launcher.zip",
                Path("ErrorLabsPlaytest.exe"),
                "a" * 64,
            ),
            LauncherUpdateAsset(
                "launcher.zip",
                "https://example.test/launcher.zip",
                100,
                None,
            ),
        )


if __name__ == "__main__":
    unittest.main()
