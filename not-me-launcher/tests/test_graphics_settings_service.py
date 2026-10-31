import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from launcher.installation_preferences import InstallationPreferences
from launcher.services.game_process_service import GameLaunchError, GameProcessService
from launcher.services.graphics_settings_service import (
    GraphicsSettingsError,
    PRESET_LEVELS,
    QUALITY_KEYS,
    apply_graphics_preset,
    game_settings_path,
)
from launcher.views.launcher_view import LauncherView


class GraphicsSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.local_data = Path(__file__).parent / "test-graphics-output"
        shutil.rmtree(self.local_data, ignore_errors=True)
        self.local_data.mkdir()
        self.path = game_settings_path(self.local_data)

    def tearDown(self) -> None:
        shutil.rmtree(self.local_data, ignore_errors=True)

    def test_each_preset_writes_all_quality_groups(self) -> None:
        for name, level in PRESET_LEVELS.items():
            with self.subTest(name=name):
                apply_graphics_preset(name, self.local_data)
                contents = self.path.read_text(encoding="utf-8")
                self.assertIn("[ScalabilityGroups]\n", contents)
                for key in QUALITY_KEYS:
                    self.assertEqual(contents.count(f"{key}={level}\n"), 1)
                self.assertIn("ResolutionSizeX=1920\n", contents)
                self.assertIn("FrameRateLimit=60.000000\n", contents)

    def test_existing_game_settings_survive_and_legacy_quality_keys_move(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            "[ScalabilityGroups]\nsg.ResolutionQuality=83\n"
            "sg.ShadowQuality=3\n\n[/Script/Engine.GameUserSettings]\n"
            "bUseVSync=True\nResolutionSizeX=2560\n"
            "sg.ShadowQuality=3\nCustomSetting=keep\n",
            encoding="utf-8",
        )
        apply_graphics_preset("low", self.local_data)
        contents = self.path.read_text(encoding="utf-8")
        self.assertEqual(contents.count("sg.ShadowQuality=0"), 1)
        self.assertNotIn("sg.ShadowQuality=3", contents)
        self.assertIn("sg.ResolutionQuality=83", contents)
        self.assertIn("bUseVSync=True", contents)
        self.assertIn("ResolutionSizeX=2560", contents)
        self.assertIn("CustomSetting=keep", contents)

    def test_batch_style_epic_config_is_migrated_to_scalability_section(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            "[/Script/Engine.GameUserSettings]\n"
            "bUseVSync=False\nsg.ShadowQuality=3\n",
            encoding="utf-8",
        )
        apply_graphics_preset("cinema", self.local_data)
        contents = self.path.read_text(encoding="utf-8")
        game_section, scalability_section = contents.split("[ScalabilityGroups]", 1)
        self.assertNotIn("sg.ShadowQuality", game_section)
        self.assertIn("sg.ShadowQuality=4", scalability_section)

    def test_invalid_preset_does_not_touch_file(self) -> None:
        with self.assertRaises(GraphicsSettingsError):
            apply_graphics_preset("ultra", self.local_data)
        self.assertFalse(self.path.exists())

    def test_game_is_not_started_if_settings_cannot_be_written(self) -> None:
        executable = self.local_data / "Alone.exe"
        executable.write_bytes(b"game")
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.local_data)}), patch(
            "launcher.services.graphics_settings_service.os.replace",
            side_effect=PermissionError("access denied"),
        ), patch("launcher.services.game_process_service.QProcess.startDetached") as start:
            with self.assertRaises(GameLaunchError):
                GameProcessService.launch(executable, "high")
        start.assert_not_called()

    def test_game_launch_writes_selected_preset_before_starting(self) -> None:
        executable = self.local_data / "Alone.exe"
        executable.write_bytes(b"game")
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.local_data)}), patch(
            "launcher.services.game_process_service.QProcess.startDetached",
            return_value=(True, 42),
        ) as start:
            self.assertEqual(GameProcessService.launch(executable, "medium"), 42)
            self.assertIn("sg.ShadowQuality=1", self.path.read_text(encoding="utf-8"))
        start.assert_called_once_with(str(executable.resolve()), [], str(executable.parent.resolve()))

    def test_launcher_selector_persists_choice(self) -> None:
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        preferences = InstallationPreferences(
            self.local_data / "installation.json", self.local_data / "legacy.json"
        )
        view = LauncherView(preferences)
        self.assertEqual(view.graphics_preset.currentData(), "epic")
        view.graphics_preset.setCurrentIndex(view.graphics_preset.findData("high"))
        self.assertEqual(preferences.graphics_preset, "high")
        self.assertEqual(
            InstallationPreferences(
                self.local_data / "installation.json", self.local_data / "legacy.json"
            ).graphics_preset,
            "high",
        )
        view.deleteLater()


if __name__ == "__main__":
    unittest.main()
