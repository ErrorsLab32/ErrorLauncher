import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from PySide6.QtCore import QObject, QStandardPaths, Signal

from launcher.config import LEGACY_INSTALLATION_STATE_PATH


class InstallationPathError(Exception):
    pass


def format_size(size: int | float) -> str:
    value = float(size)
    units = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "Б" or (unit in {"КБ", "МБ"} and value.is_integer()):
                formatted = str(int(value))
            else:
                formatted = f"{value:.1f}".replace(".", ",")
            return f"{formatted} {unit}"
        value /= 1024
    return f"{value:.1f} ТБ".replace(".", ",")


def safe_tag_name(tag_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", tag_name).strip("._")
    if not safe:
        raise InstallationPathError("Некорректный тег релиза.")
    return safe


class InstallationPreferences(QObject):
    install_path_changed = Signal(object)
    download_active_changed = Signal(bool)
    launch_on_windows_start_changed = Signal(bool)
    SAFETY_MARGIN_BYTES = 512 * 1024 * 1024

    def __init__(
        self,
        state_path: Path | None = None,
        legacy_state_path: Path = LEGACY_INSTALLATION_STATE_PATH,
    ) -> None:
        super().__init__()
        if state_path is None:
            app_data = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            if not app_data:
                raise InstallationPathError(
                    "Не удалось определить каталог данных приложения."
                )
            state_path = Path(app_data) / "installation.json"
        self.state_path = state_path.expanduser().resolve()
        self._legacy_state_path = legacy_state_path
        self._installed_version: str | None = None
        self._install_path: Path | None = None
        self._executable_path: Path | None = None
        self._download_active = False
        self._installed_size_bytes: int | None = None
        self._launch_on_windows_start = True
        self._tray_close_notice_shown = False
        self._load()

    @property
    def installed_version(self) -> str | None:
        return self._installed_version

    @property
    def install_path(self) -> Path | None:
        return self._install_path

    @property
    def executable_path(self) -> Path | None:
        return self._executable_path

    @property
    def installation_recorded(self) -> bool:
        return self._installed_version is not None or self._executable_path is not None

    @property
    def installed_executable(self) -> Path | None:
        if self._install_path is None or self._executable_path is None:
            return None
        candidate = (self._install_path / self._executable_path).resolve()
        try:
            candidate.relative_to(self._install_path)
        except ValueError:
            return None
        return candidate

    @property
    def installation_is_valid(self) -> bool:
        executable = self.installed_executable
        return (
            self._installed_version is not None
            and self._install_path is not None
            and self._install_path.is_dir()
            and executable is not None
            and executable.is_file()
        )

    @property
    def download_active(self) -> bool:
        return self._download_active

    @property
    def installed_size_bytes(self) -> int | None:
        return self._installed_size_bytes

    @property
    def launch_on_windows_start(self) -> bool:
        return self._launch_on_windows_start

    @property
    def tray_close_notice_shown(self) -> bool:
        return self._tray_close_notice_shown

    def set_launch_on_windows_start(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._launch_on_windows_start == enabled:
            return
        self._launch_on_windows_start = enabled
        self._save()
        self.launch_on_windows_start_changed.emit(enabled)

    def mark_tray_close_notice_shown(self) -> None:
        if not self._tray_close_notice_shown:
            self._tray_close_notice_shown = True
            self._save()

    def current_installed_size_bytes(self) -> int | None:
        if self._installed_size_bytes is not None:
            return self._installed_size_bytes
        if self._install_path is None:
            return None
        game_directory = self._install_path / "game"
        if not game_directory.is_dir():
            return None
        try:
            size = sum(path.stat().st_size for path in game_directory.rglob("*") if path.is_file())
        except OSError:
            return None
        self._installed_size_bytes = size
        self._save()
        return size

    def validate_and_set_install_path(self, path: Path) -> Path:
        normalized = path.expanduser().resolve()
        probe_path: Path | None = None
        try:
            normalized.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".errorlabs-write-",
                suffix=".tmp",
                dir=normalized,
                delete=False,
            ) as probe:
                probe.write(b"ok")
                probe.flush()
                probe_path = Path(probe.name)
            probe_path.unlink()
            (normalized / ".errorlabs-playtest" / "downloads").mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            if probe_path is not None:
                probe_path.unlink(missing_ok=True)
            raise InstallationPathError(
                "Нет доступа для записи в выбранную папку. Выберите другую папку."
            ) from error
        self._install_path = normalized
        self._save()
        self.install_path_changed.emit(normalized)
        return normalized

    def release_download_directory(self, tag_name: str) -> Path:
        if self._install_path is None:
            raise InstallationPathError("Папка установки не выбрана.")
        return (
            self._install_path
            / ".errorlabs-playtest"
            / "downloads"
            / safe_tag_name(tag_name)
        ).resolve()

    def ensure_free_space(self, asset_size: int) -> None:
        if self._install_path is None:
            raise InstallationPathError("Папка установки не выбрана.")
        required = asset_size + self.SAFETY_MARGIN_BYTES
        try:
            available = shutil.disk_usage(self._install_path).free
        except OSError as error:
            raise InstallationPathError(
                "Не удалось определить свободное место в выбранной папке."
            ) from error
        if available < required:
            raise InstallationPathError(
                "Недостаточно свободного места. "
                f"Для загрузки требуется {format_size(required)}, "
                f"доступно {format_size(available)}."
            )

    def set_download_active(self, active: bool) -> None:
        if self._download_active == active:
            return
        self._download_active = active
        self.download_active_changed.emit(active)

    def mark_installation_complete(
        self,
        installed_version: str,
        executable_path: Path,
        installed_size_bytes: int | None = None,
    ) -> None:
        if self._install_path is None:
            raise InstallationPathError("Папка установки не выбрана.")
        if executable_path.is_absolute() or ".." in executable_path.parts:
            raise InstallationPathError("Некорректный путь к исполняемому файлу игры.")
        absolute_executable = (self._install_path / executable_path).resolve()
        try:
            absolute_executable.relative_to(self._install_path)
        except ValueError as error:
            raise InstallationPathError(
                "Некорректный путь к исполняемому файлу игры."
            ) from error
        if not absolute_executable.is_file():
            raise InstallationPathError("Исполняемый файл игры не найден.")

        previous_version = self._installed_version
        previous_executable = self._executable_path
        previous_size = self._installed_size_bytes
        self._installed_version = installed_version
        self._executable_path = executable_path
        self._installed_size_bytes = installed_size_bytes
        try:
            self._save()
        except InstallationPathError:
            self._installed_version = previous_version
            self._executable_path = previous_executable
            self._installed_size_bytes = previous_size
            raise

    def _load(self) -> None:
        source = self.state_path if self.state_path.is_file() else self._legacy_state_path
        data: dict[str, object] = {}
        try:
            if source.is_file():
                loaded = json.loads(source.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
        installed_version = data.get("installed_version")
        install_path = data.get("install_path")
        executable_path = data.get("executable_path")
        installed_size_bytes = data.get("installed_size_bytes")
        launch_on_windows_start = data.get("launch_on_windows_start", True)
        self._tray_close_notice_shown = data.get("tray_close_notice_shown") is True
        self._launch_on_windows_start = launch_on_windows_start is not False
        self._installed_version = (
            installed_version
            if isinstance(installed_version, str) and installed_version
            else None
        )
        self._install_path = (
            Path(install_path).expanduser().resolve()
            if isinstance(install_path, str) and install_path
            else None
        )
        parsed_executable = (
            Path(executable_path)
            if isinstance(executable_path, str) and executable_path
            else None
        )
        self._executable_path = (
            parsed_executable
            if parsed_executable is not None
            and not parsed_executable.is_absolute()
            and ".." not in parsed_executable.parts
            else None
        )
        self._installed_size_bytes = (
            installed_size_bytes if isinstance(installed_size_bytes, int)
            and not isinstance(installed_size_bytes, bool) and installed_size_bytes >= 0 else None
        )
        if not self.state_path.is_file():
            self._save()

    def _save(self) -> None:
        payload = {
            "installed_version": self._installed_version,
            "install_path": str(self._install_path) if self._install_path else None,
            "executable_path": (
                str(self._executable_path) if self._executable_path else None
            ),
            "installed_size_bytes": self._installed_size_bytes,
            "launch_on_windows_start": self._launch_on_windows_start,
            "tray_close_notice_shown": self._tray_close_notice_shown,
        }
        temporary_path: Path | None = None
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{self.state_path.name}.",
                suffix=".tmp",
                dir=self.state_path.parent,
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, self.state_path)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise InstallationPathError(
                "Не удалось сохранить выбранную папку установки."
            ) from error
