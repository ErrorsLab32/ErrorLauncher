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

    def test_packaged_command_uses_stable_install_executable(self) -> None:
        with patch.object(sys, "frozen", True, create=True), patch(
            "launcher.services.autostart_service.installed_launcher_path",
            return_value=Path("C:/App Space/Programs/ErrorLabs Playtest/ErrorLabsPlaytest.exe"),
        ):
            command = AutostartService.command()
        self.assertEqual(command, '"C:\\App Space\\Programs\\ErrorLabs Playtest\\ErrorLabsPlaytest.exe" --background')

    def test_registry_failure_is_returned(self) -> None:
        service = AutostartService()
        with patch("launcher.services.autostart_service.os.name", "nt"), patch.dict(sys.modules, {"winreg": None}):
            self.assertIsNotNone(service.apply(True))

    def test_enabled_autostart_replaces_old_target_and_keeps_background(self) -> None:
        registry = FakeWinreg({"NotMeLauncher": '"C:\\Old Version\\ErrorLabsPlaytest.exe" --background'})

        result = self._reconcile(registry, True, "C:/New Version/ErrorLabsPlaytest.exe")

        self.assertTrue(result.enabled)
        self.assertEqual(result.old_target, '"C:\\Old Version\\ErrorLabsPlaytest.exe" --background')
        self.assertEqual(registry.values["NotMeLauncher"], '"C:\\New Version\\ErrorLabsPlaytest.exe" --background')
        self.assertTrue(registry.values["NotMeLauncher"].endswith(" --background"))
        self.assertTrue(result.corrected)

    def test_disabled_autostart_remains_disabled_and_removes_owned_duplicates(self) -> None:
        registry = FakeWinreg(
            {
                "NotMeLauncher": '"C:\\Old\\ErrorLabsPlaytest.exe" --background',
                "ErrorLabsPlaytest-0.1.0": '"C:\\Old\\ErrorLabsPlaytest.exe" --background',
                "Spotify": '"C:\\Spotify\\Spotify.exe" --autostart',
            }
        )

        result = self._reconcile(registry, False, "C:/New/ErrorLabsPlaytest.exe")

        self.assertFalse(result.enabled)
        self.assertNotIn("NotMeLauncher", registry.values)
        self.assertNotIn("ErrorLabsPlaytest-0.1.0", registry.values)
        self.assertEqual(registry.values["Spotify"], '"C:\\Spotify\\Spotify.exe" --autostart')
        self.assertEqual(result.removed_obsolete, ("ErrorLabsPlaytest-0.1.0",))

    def test_obsolete_version_specific_entries_are_removed_without_duplicates(self) -> None:
        registry = FakeWinreg(
            {
                "NotMeLauncher": '"C:\\New\\ErrorLabsPlaytest.exe" --background',
                "ErrorLabs Playtest 0.1.0": '"C:\\Old\\ErrorLabsPlaytest.exe" --background',
                "OtherApp": '"C:\\Other\\app.exe"',
            }
        )

        result = self._reconcile(registry, True, "C:/New/ErrorLabsPlaytest.exe")

        self.assertFalse(result.corrected)
        self.assertEqual(result.removed_obsolete, ("ErrorLabs Playtest 0.1.0",))
        self.assertEqual(list(registry.values), ["NotMeLauncher", "OtherApp"])

    def test_updater_path_is_never_written_to_autostart(self) -> None:
        registry = FakeWinreg({"NotMeLauncher": '"C:\\Old\\ErrorLabsPlaytest.exe" --background'})

        result = self._reconcile(
            registry,
            True,
            "C:/Users/Test/AppData/Local/ErrorLabs/updater-runtime/1.0/ErrorLabsUpdater.exe",
        )

        self.assertIsNotNone(result.warning)
        self.assertEqual(registry.values["NotMeLauncher"], '"C:\\Old\\ErrorLabsPlaytest.exe" --background')

    def test_repeated_start_is_idempotent_for_current_packaged_executable(self) -> None:
        registry = FakeWinreg({"NotMeLauncher": '"C:\\New Version\\ErrorLabsPlaytest.exe" --background'})

        first = self._reconcile(registry, True, "C:/New Version/ErrorLabsPlaytest.exe")
        second = self._reconcile(registry, True, "C:/New Version/ErrorLabsPlaytest.exe")

        self.assertFalse(first.corrected)
        self.assertFalse(second.corrected)
        self.assertEqual(registry.set_calls, [])

    @staticmethod
    def _reconcile(registry, enabled: bool, executable: str):  # type: ignore[no-untyped-def]
        with patch.dict(sys.modules, {"winreg": registry}), patch.object(
            sys, "frozen", True, create=True
        ), patch(
            "launcher.services.autostart_service.installed_launcher_path",
            return_value=Path(executable),
        ), patch(
            "launcher.services.autostart_service.is_forbidden_launcher_path",
            return_value=False,
        ), patch.object(Path, "is_file", return_value=True):
            return AutostartService().reconcile(enabled)


class FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self, values: dict[str, str]) -> None:
        self.values = dict(values)
        self.set_calls: list[tuple[str, str]] = []

    def OpenKey(self, *_args):  # type: ignore[no-untyped-def]
        return FakeRegistryKey(self)

    def CreateKey(self, *_args):  # type: ignore[no-untyped-def]
        return FakeRegistryKey(self)

    def EnumValue(self, _key, index: int):  # type: ignore[no-untyped-def]
        try:
            name = list(self.values)[index]
        except IndexError as error:
            raise OSError from error
        return name, self.values[name], self.REG_SZ

    def SetValueEx(self, _key, name: str, _reserved: int, _kind: int, value: str) -> None:  # type: ignore[no-untyped-def]
        self.values[name] = value
        self.set_calls.append((name, value))

    def DeleteValue(self, _key, name: str) -> None:  # type: ignore[no-untyped-def]
        del self.values[name]


class FakeRegistryKey:
    def __init__(self, registry: FakeWinreg) -> None:
        self.registry = registry

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:  # type: ignore[no-untyped-def]
        return None


if __name__ == "__main__":
    unittest.main()
