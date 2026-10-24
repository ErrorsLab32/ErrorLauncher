from dataclasses import dataclass
from pathlib import Path
import os
import re
import sys

from launcher.runtime_paths import installed_launcher_path, is_forbidden_launcher_path


@dataclass(frozen=True)
class AutostartSyncResult:
    enabled: bool
    old_target: str | None
    new_target: str | None
    corrected: bool
    removed_obsolete: tuple[str, ...]
    warning: str | None = None


class AutostartService:
    VALUE_NAME = "NotMeLauncher"
    KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _OWN_VALUE_NAME = re.compile(r"(?:errorlabs|not[ _-]?me)", re.IGNORECASE)
    _OWN_EXECUTABLE = re.compile(
        r"(?:errorlabsplaytest|not[ _-]?me(?:launcher)?|errorlabsupdater)\.exe",
        re.IGNORECASE,
    )

    @staticmethod
    def command(entrypoint: Path | None = None) -> str:
        if getattr(sys, "frozen", False):
            executable = installed_launcher_path()
            return f'"{executable}" --background'
        entrypoint = entrypoint or Path(sys.argv[0]).resolve()
        interpreter = Path(sys.executable).resolve()
        pythonw = interpreter.with_name("pythonw.exe")
        if pythonw.is_file():
            interpreter = pythonw
        return f'"{interpreter}" "{entrypoint}" --background'

    def apply(self, enabled: bool, entrypoint: Path | None = None) -> str | None:
        """Compatibility wrapper for callers that only need an error message."""
        return self.reconcile(enabled, entrypoint).warning

    def reconcile(
        self,
        enabled: bool,
        entrypoint: Path | None = None,
    ) -> AutostartSyncResult:
        """Keep exactly one owned Run value in sync with the running launcher."""
        if os.name != "nt":
            return AutostartSyncResult(enabled, None, None, False, ())
        try:
            import winreg

            with self._open_run_key(winreg) as key:
                values = self._read_values(winreg, key)
                owned = {
                    name: value
                    for name, value in values.items()
                    if self._is_own_entry(name, value)
                }
                old_target = owned.get(self.VALUE_NAME)
                obsolete = tuple(name for name in owned if name != self.VALUE_NAME)

                if not enabled:
                    for name in owned:
                        winreg.DeleteValue(key, name)
                    return AutostartSyncResult(
                        False, old_target, None, bool(owned), obsolete
                    )

                new_target = self.command(entrypoint)
                if self._is_updater_or_staging_target(new_target):
                    raise OSError("refusing to register updater or staging executable")
                if getattr(sys, "frozen", False):
                    stable_launcher = installed_launcher_path()
                    if is_forbidden_launcher_path(stable_launcher) or not stable_launcher.is_file():
                        raise OSError(f"stable installed launcher is unavailable: {stable_launcher}")
                corrected = old_target != new_target
                if corrected:
                    winreg.SetValueEx(
                        key, self.VALUE_NAME, 0, winreg.REG_SZ, new_target
                    )
                for name in obsolete:
                    winreg.DeleteValue(key, name)
                return AutostartSyncResult(
                    True, old_target, new_target, corrected, obsolete
                )
        except (OSError, ImportError, AttributeError) as error:
            return AutostartSyncResult(
                enabled,
                None,
                None,
                False,
                (),
                f"Не удалось обновить автозапуск Windows: {error}",
            )

    def _open_run_key(self, winreg):  # type: ignore[no-untyped-def]
        access = winreg.KEY_READ | winreg.KEY_SET_VALUE
        try:
            return winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, access)
        except FileNotFoundError:
            return winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH)

    @staticmethod
    def _read_values(winreg, key) -> dict[str, str]:  # type: ignore[no-untyped-def]
        values: dict[str, str] = {}
        index = 0
        while True:
            try:
                name, value, _kind = winreg.EnumValue(key, index)
            except OSError:
                return values
            if isinstance(value, str):
                values[name] = value
            index += 1

    @classmethod
    def _is_own_entry(cls, name: str, target: str) -> bool:
        return bool(cls._OWN_VALUE_NAME.search(name) or cls._OWN_EXECUTABLE.search(target))

    @staticmethod
    def _is_updater_or_staging_target(target: str) -> bool:
        normalized = target.replace("/", "\\").lower()
        return (
            "errorlabsupdater.exe" in normalized
            or "\\updater-runtime\\" in normalized
            or "\\.errorlabs-updater\\" in normalized
            or "\\appdata\\local\\temp\\" in normalized
            or "\\_mei" in normalized
        )
