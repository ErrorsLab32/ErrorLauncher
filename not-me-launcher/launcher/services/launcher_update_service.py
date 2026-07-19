from collections.abc import Callable
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QStandardPaths
import requests

from launcher.models.launcher_update import (
    LauncherUpdateAsset,
    LauncherUpdateManifest,
    LauncherUpdateProgress,
    LauncherUpdateRelease,
)


ProgressCallback = Callable[[LauncherUpdateProgress], None]
CancellationCallback = Callable[[], bool]


class LauncherUpdateError(Exception):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def normalize_version(value: str) -> Version:
    normalized = value.strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:]
    try:
        return Version(normalized)
    except InvalidVersion as error:
        raise LauncherUpdateError(
            f"Некорректная версия обновления лаунчера: {value}"
        ) from error


def launcher_local_data_path() -> Path:
    override = os.getenv("ERRORLABS_LOCAL_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    if not location:
        raise LauncherUpdateError(
            "Не удалось определить каталог обновлений лаунчера."
        )
    return Path(location).expanduser().resolve()


class LauncherUpdateService:
    API_VERSION = "2022-11-28"
    USER_AGENT = "ErrorLabs-Playtest-Launcher"
    MANIFEST_NAME = "launcher-manifest.json"
    PLATFORM = "windows-x64"

    def __init__(
        self,
        repository: str,
        cache_root: Path | None = None,
        session: requests.Session | None = None,
        connect_timeout: float = 10.0,
        read_timeout: float = 60.0,
    ) -> None:
        if repository != "ErrorsLab32/ErrorLauncher":
            raise LauncherUpdateError(
                "Некорректно настроен репозиторий обновлений лаунчера."
            )
        self.repository = repository
        self.cache_root = (
            cache_root.expanduser().resolve()
            if cache_root is not None
            else launcher_local_data_path() / "launcher-updates"
        )
        self._session = session or requests.Session()
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self.log_path = self.cache_root.parent / "logs" / "launcher-update.log"

    def check_for_update(
        self,
        current_version: str,
    ) -> LauncherUpdateRelease | None:
        url = f"https://api.github.com/repos/{self.repository}/releases/latest"
        try:
            response = self._session.get(
                url,
                headers=self._github_headers(),
                timeout=(self._connect_timeout, self._read_timeout),
            )
        except requests.Timeout as error:
            raise LauncherUpdateError(
                "Не удалось проверить обновление лаунчера: сервер не ответил вовремя."
            ) from error
        except requests.RequestException as error:
            raise LauncherUpdateError(
                "Не удалось проверить обновление лаунчера."
            ) from error
        self._raise_for_status(response)
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("release is not an object")
            tag_name = str(payload["tag_name"])
            assets_data = payload["assets"]
            if not isinstance(assets_data, list):
                raise TypeError("assets is not an array")
            assets = tuple(self._parse_asset(value) for value in assets_data)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LauncherUpdateError(
                "GitHub вернул некорректное описание релиза лаунчера."
            ) from error

        manifest_asset = next(
            (asset for asset in assets if asset.name == self.MANIFEST_NAME),
            None,
        )
        if manifest_asset is None:
            raise LauncherUpdateError(
                "В релизе отсутствует launcher-manifest.json."
            )
        manifest = self._download_manifest(manifest_asset)
        remote_version = normalize_version(manifest.version)
        tag_version = normalize_version(tag_name)
        installed_version = normalize_version(current_version)
        if tag_version != remote_version:
            raise LauncherUpdateError(
                "Версия manifest не соответствует версии GitHub Release."
            )
        package = next(
            (asset for asset in assets if asset.name == manifest.asset),
            None,
        )
        if package is None:
            raise LauncherUpdateError(
                "В релизе отсутствует пакет, указанный в launcher-manifest.json."
            )
        if package.digest:
            digest = package.digest.lower()
            if digest.startswith("sha256:") and digest[7:] != manifest.sha256:
                raise LauncherUpdateError(
                    "SHA-256 пакета не совпадает с данными GitHub Release."
                )
        if remote_version <= installed_version:
            return None
        return LauncherUpdateRelease(tag_name, manifest, package)

    def download_update(
        self,
        release: LauncherUpdateRelease,
        progress_callback: ProgressCallback,
        is_cancelled: CancellationCallback = lambda: False,
    ) -> Path:
        version = str(normalize_version(release.manifest.version))
        destination = (self.cache_root / version).resolve()
        self._require_inside(destination, self.cache_root)
        destination.mkdir(parents=True, exist_ok=True)
        package_path = (destination / release.package.name).resolve()
        self._require_inside(package_path, destination)
        partial_path = package_path.with_name(package_path.name + ".part")
        if package_path.is_file() and self._verified_package(package_path, release):
            progress_callback(
                LauncherUpdateProgress(release.package.size, release.package.size)
            )
            return package_path
        package_path.unlink(missing_ok=True)
        partial_path.unlink(missing_ok=True)

        try:
            response = self._session.get(
                release.package.url,
                headers=self._asset_headers(),
                stream=True,
                allow_redirects=True,
                timeout=(self._connect_timeout, self._read_timeout),
            )
        except requests.Timeout as error:
            raise LauncherUpdateError(
                "Сервер обновлений лаунчера не ответил вовремя."
            ) from error
        except requests.RequestException as error:
            raise LauncherUpdateError(
                "Не удалось скачать обновление лаунчера."
            ) from error
        self._raise_for_status(response)
        downloaded = 0
        digest = hashlib.sha256()
        try:
            with response, partial_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if is_cancelled():
                        raise LauncherUpdateError("Загрузка обновления отменена.")
                    if not chunk:
                        continue
                    output.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    progress_callback(
                        LauncherUpdateProgress(downloaded, release.package.size)
                    )
                output.flush()
                os.fsync(output.fileno())
        except OSError as error:
            partial_path.unlink(missing_ok=True)
            raise LauncherUpdateError(
                "Не удалось сохранить обновление лаунчера."
            ) from error
        if downloaded != release.package.size:
            partial_path.unlink(missing_ok=True)
            raise LauncherUpdateError(
                "Пакет обновления лаунчера загружен не полностью."
            )
        if digest.hexdigest().lower() != release.manifest.sha256.lower():
            partial_path.unlink(missing_ok=True)
            raise LauncherUpdateError(
                "Проверка целостности обновления лаунчера не пройдена."
            )
        os.replace(partial_path, package_path)
        return package_path

    def log(self, message: str) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass

    def _download_manifest(
        self,
        asset: LauncherUpdateAsset,
    ) -> LauncherUpdateManifest:
        try:
            response = self._session.get(
                asset.url,
                headers=self._asset_headers(),
                allow_redirects=True,
                timeout=(self._connect_timeout, self._read_timeout),
            )
        except requests.Timeout as error:
            raise LauncherUpdateError(
                "Не удалось загрузить описание обновления лаунчера."
            ) from error
        except requests.RequestException as error:
            raise LauncherUpdateError(
                "Не удалось загрузить описание обновления лаунчера."
            ) from error
        self._raise_for_status(response)
        try:
            data = response.json()
        except (requests.JSONDecodeError, json.JSONDecodeError, ValueError) as error:
            raise LauncherUpdateError(
                "launcher-manifest.json содержит некорректный JSON."
            ) from error
        return self.parse_manifest(data)

    @classmethod
    def parse_manifest(cls, data: object) -> LauncherUpdateManifest:
        if not isinstance(data, dict):
            raise LauncherUpdateError("launcher-manifest.json должен быть объектом.")
        required = ("version", "platform", "asset", "entrypoint", "sha256")
        if any(not isinstance(data.get(field), str) or not data[field] for field in required):
            raise LauncherUpdateError(
                "launcher-manifest.json не содержит обязательные поля."
            )
        version = str(data["version"])
        normalize_version(version)
        platform = str(data["platform"])
        if platform != cls.PLATFORM:
            raise LauncherUpdateError("Платформа обновления лаунчера не поддерживается.")
        asset = str(data["asset"])
        if Path(asset).name != asset or not asset.lower().endswith(".zip"):
            raise LauncherUpdateError("Некорректное имя ZIP-пакета лаунчера.")
        entrypoint_text = str(data["entrypoint"])
        cls._validate_relative_path(entrypoint_text)
        sha256 = str(data["sha256"]).lower()
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise LauncherUpdateError("Некорректный SHA-256 пакета лаунчера.")
        return LauncherUpdateManifest(
            version,
            platform,
            asset,
            Path(PurePosixPath(entrypoint_text)),
            sha256,
        )

    @staticmethod
    def _validate_relative_path(value: str) -> None:
        posix = PurePosixPath(value.replace("\\", "/"))
        windows = PureWindowsPath(value)
        if (
            posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or not posix.parts
        ):
            raise LauncherUpdateError(
                "Некорректный путь entrypoint в launcher-manifest.json."
            )

    @staticmethod
    def _parse_asset(data: object) -> LauncherUpdateAsset:
        if not isinstance(data, dict):
            raise TypeError("asset is not an object")
        name = data["name"]
        url = data["browser_download_url"]
        size = data["size"]
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("invalid asset name")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("invalid asset URL")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError("invalid asset size")
        digest = data.get("digest")
        return LauncherUpdateAsset(
            name,
            url,
            size,
            str(digest) if digest else None,
        )

    def _verified_package(
        self,
        path: Path,
        release: LauncherUpdateRelease,
    ) -> bool:
        try:
            if path.stat().st_size != release.package.size:
                return False
            digest = hashlib.sha256()
            with path.open("rb") as package:
                for chunk in iter(lambda: package.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest().lower() == release.manifest.sha256.lower()
        except OSError:
            return False

    @classmethod
    def _github_headers(cls) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": cls.API_VERSION,
            "User-Agent": cls.USER_AGENT,
        }

    @classmethod
    def _asset_headers(cls) -> dict[str, str]:
        return {"User-Agent": cls.USER_AGENT}

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.status_code == 404:
            raise LauncherUpdateError("Релиз обновления лаунчера не найден.")
        if response.status_code == 403:
            raise LauncherUpdateError(
                "Проверка обновления лаунчера временно недоступна."
            )
        if response.status_code >= 400:
            raise LauncherUpdateError(
                f"Сервис обновлений лаунчера вернул HTTP {response.status_code}."
            )

    @staticmethod
    def _require_inside(path: Path, parent: Path) -> None:
        try:
            path.relative_to(parent)
        except ValueError as error:
            raise LauncherUpdateError("Некорректный путь обновления лаунчера.") from error
