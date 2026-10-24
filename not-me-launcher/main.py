from datetime import datetime
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import traceback

from launcher.runtime_paths import (
    install_directory,
    installed_launcher_path,
    installed_updater_path,
    runtime_meipass,
    updater_staging_root,
    is_forbidden_launcher_path,
)


def _startup_crash_log_path() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    root = Path(local_app_data) if local_app_data else Path.cwd()
    return root / "ErrorLabs" / "ErrorLabs Playtest" / "logs" / "startup-crash.log"


def _write_startup_crash(error: BaseException) -> None:
    try:
        path = _startup_crash_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] startup failure\n")
            output.write(f"executable: {sys.executable}\n")
            output.write("".join(traceback.format_exception(error)))
            output.write("\n")
    except OSError:
        pass


def _startup_log_path() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    root = Path(local_app_data) if local_app_data else Path.cwd()
    return root / "ErrorLabs" / "ErrorLabs Playtest" / "logs" / "launcher.log"


def _registered_autostart_target() -> str:
    if os.name != "nt":
        return "<non-windows>"
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as key:
            return str(winreg.QueryValueEx(key, "NotMeLauncher")[0])
    except (OSError, ImportError):
        return "<not registered>"


def _shortcut_targets() -> str:
    if os.name != "nt":
        return "<non-windows>"
    script = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$links = @(
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'ErrorLabs Playtest\ErrorLabs Playtest.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'ErrorLabs Playtest.lnk')
)
$targets = @($links | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    $link = $shell.CreateShortcut($_)
    @{ shortcut = $_; target = $link.TargetPath; working_directory = $link.WorkingDirectory }
})
ConvertTo-Json -InputObject $targets -Compress
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return json.dumps(json.loads(result.stdout), ensure_ascii=False)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return "<shortcut inspection unavailable>"


def _write_startup_diagnostics() -> None:
    """Record every path involved in packaged startup before application code runs."""
    meipass = runtime_meipass()
    stable_launcher = installed_launcher_path()
    lines = [
        "startup diagnostics",
        f"real_executable={Path(sys.executable).resolve()}",
        f"argv0={Path(sys.argv[0]).resolve() if sys.argv else '<missing>'}",
        f"cwd={Path.cwd().resolve()}",
        f"__file__={Path(__file__).resolve()}",
        f"pyinstaller_meipass={meipass or '<absent>'}",
        f"install_directory={install_directory()}",
        f"stable_launcher={stable_launcher}",
        f"expected_shortcut_target={stable_launcher}",
        f"shortcut_targets={_shortcut_targets()}",
        f"autostart_target={_registered_autostart_target()}",
        f"updater_target={installed_updater_path()}",
        f"updater_staging_root={updater_staging_root()}",
        f"updater_runtime_root={(Path(os.getenv('ERRORLABS_LOCAL_DATA_DIR')) if os.getenv('ERRORLABS_LOCAL_DATA_DIR') else _startup_log_path().parent.parent) / 'updater-runtime'}",
        f"temp_directory={Path(tempfile.gettempdir()).resolve()}",
    ]
    try:
        path = _startup_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}]\n")
            output.write("\n".join(lines) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        _write_startup_diagnostics()
        if getattr(sys, "frozen", False):
            stable_launcher = installed_launcher_path()
            if is_forbidden_launcher_path(stable_launcher):
                raise RuntimeError(f"Unsafe install directory: {stable_launcher.parent}")
            if Path(sys.executable).resolve() != stable_launcher:
                if not stable_launcher.is_file():
                    raise RuntimeError("Install ErrorLabs Playtest using Setup before running the launcher.")
                environment = os.environ.copy()
                environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                subprocess.Popen(
                    [str(stable_launcher), *sys.argv[1:]],
                    cwd=str(stable_launcher.parent),
                    env=environment,
                    close_fds=True,
                )
                return 0
        from launcher.app import run

        return run()
    except BaseException as error:
        _write_startup_crash(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
