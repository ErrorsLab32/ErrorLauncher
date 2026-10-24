"""Stable paths for the packaged launcher and its update lifecycle."""

import os
from pathlib import Path
import tempfile


INSTALL_DIRECTORY_NAME = "ErrorLabs Playtest"
LAUNCHER_EXECUTABLE_NAME = "ErrorLabsPlaytest.exe"
UPDATER_EXECUTABLE_NAME = "ErrorLabsUpdater.exe"


def install_directory() -> Path:
    """Return the only directory that may contain the installed launcher."""
    local_app_data = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return (root / "Programs" / INSTALL_DIRECTORY_NAME).resolve()


def installed_launcher_path() -> Path:
    return install_directory() / LAUNCHER_EXECUTABLE_NAME


def installed_updater_path() -> Path:
    return install_directory() / UPDATER_EXECUTABLE_NAME


def runtime_meipass() -> Path | None:
    value = getattr(__import__("sys"), "_MEIPASS", None)
    return Path(value).resolve() if value else None


def updater_staging_root() -> Path:
    # The install directory itself must be renameable while updating. Keep
    # staging/backup beside it, never inside the directory being replaced.
    return install_directory().parent / ".errorlabs-updater"


def is_forbidden_launcher_path(path: Path) -> bool:
    """Reject TEMP, PyInstaller onefile, cache, and updater staging paths."""
    candidate = path.expanduser().resolve()
    forbidden_roots = [Path(tempfile.gettempdir()).resolve(), updater_staging_root()]
    meipass = runtime_meipass()
    if meipass is not None:
        forbidden_roots.append(meipass)
    for root in forbidden_roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return any(part.upper().startswith("_MEI") for part in candidate.parts)
