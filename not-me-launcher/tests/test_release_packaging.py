from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InstallerDefinitionTests(unittest.TestCase):
    def test_installer_is_per_user_and_uses_a_stable_identity(self) -> None:
        content = (PROJECT_ROOT / "installer" / "ErrorLabsPlaytest.iss").read_text(encoding="utf-8")

        self.assertIn("AppId={#MyAppId}", content)
        self.assertIn("PrivilegesRequired=lowest", content)
        self.assertIn("DefaultDirName={localappdata}\\Programs\\ErrorLabs Playtest", content)
        self.assertIn("ErrorLabsPlaytest.exe", content)
        self.assertIn("CloseApplications=yes", content)
        self.assertIn("UninstallDisplayName=Удалить ErrorLabs Playtest", content)

    def test_installer_has_only_launcher_shortcuts_and_opt_in_desktop_shortcut(self) -> None:
        content = (PROJECT_ROOT / "installer" / "ErrorLabsPlaytest.iss").read_text(encoding="utf-8")

        self.assertIn("Name: \"desktopicon\"", content)
        self.assertIn("Flags: unchecked", content)
        self.assertIn("Name: \"{group}\\ErrorLabs Playtest\"", content)
        self.assertIn("WorkingDir: \"{app}\"", content)
        self.assertNotIn("ErrorLabsUpdater.exe\"; Description", content)


class PackagingScriptTests(unittest.TestCase):
    def test_packaging_script_creates_all_three_release_assets(self) -> None:
        content = (PROJECT_ROOT / "scripts" / "package_launcher_release.ps1").read_text(encoding="utf-8")

        self.assertIn("Find-InnoSetupCompiler", content)
        self.assertIn("Inno Setup не установлен", content)
        self.assertIn("ErrorLabsPlaytestSetup-$normalizedVersion.exe", content)
        self.assertIn("ErrorLabsPlaytest-$normalizedVersion-win-x64.zip", content)
        self.assertIn("launcher-manifest.json", content)
        self.assertIn('Join-Path $projectRoot "release"', content)
        self.assertIn("GAME_RELEASES_TOKEN must be set", content)
        self.assertIn("BUILT_GAME_RELEASES_TOKEN_B64", content)

    def test_pyinstaller_spec_is_available_to_ci(self) -> None:
        spec_file = PROJECT_ROOT / "ErrorLabsPlaytest.spec"
        self.assertTrue(spec_file.is_file())
        content = spec_file.read_text(encoding="utf-8")
        self.assertIn("ErrorLabsPlaytest", content)
        self.assertIn("ErrorLabsUpdater", content)


if __name__ == "__main__":
    unittest.main()
