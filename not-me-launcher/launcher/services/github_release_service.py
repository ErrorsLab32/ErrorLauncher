from collections.abc import Callable
from pathlib import Path
import re
import time

import requests

from launcher.config import GitHubConfig
from launcher.models.release_info import DownloadProgress, ReleaseAsset, ReleaseInfo


ProgressCallback = Callable[[DownloadProgress], None]
CancellationCallback = Callable[[], bool]


class GitHubReleaseError(Exception):
    def __init__(self, user_message: str, status_code: int | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


def natural_sort_key(value: str) -> list[tuple[int, object]]:
    return [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
    ]


class GitHubReleaseService:
    API_ROOT = "https://api.github.com"
    API_VERSION = "2022-11-28"
    USER_AGENT = "ErrorLabs-Playtest-Launcher"

    def __init__(self, config: GitHubConfig) -> None:
        self._config = config
        self._session = requests.Session()

    def get_latest_release(self) -> ReleaseInfo:
        self._require_configuration()
        url = f"{self.API_ROOT}/repos/{self._config.repository}/releases/latest"
        try:
            response = self._session.get(
                url,
                headers=self._json_headers(),
                timeout=(self._config.connect_timeout, self._config.read_timeout),
            )
        except requests.Timeout as error:
            raise GitHubReleaseError(
                "GitHub не ответил вовремя. Повторите попытку."
            ) from error
        except requests.RequestException as error:
            raise GitHubReleaseError(
                "Не удалось подключиться к GitHub. Проверьте соединение и повторите попытку."
            ) from error
        self._raise_for_status(response)
        try:
            data = response.json()
            assets_data = data["assets"]
            if not isinstance(assets_data, list):
                raise TypeError("assets is not a list")
            assets = tuple(
                sorted(
                    (self._parse_asset(item) for item in assets_data),
                    key=lambda asset: natural_sort_key(asset.name),
                )
            )
            if not assets:
                raise GitHubReleaseError("В последнем релизе нет файлов сборки.")
            release = ReleaseInfo(
                tag_name=str(data["tag_name"]),
                name=str(data.get("name") or data["tag_name"]),
                body=str(data.get("body") or ""),
                published_at=str(data.get("published_at") or ""),
                assets=assets,
                http_status=response.status_code,
            )
        except GitHubReleaseError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise GitHubReleaseError(
                "GitHub вернул неполные данные опубликованного релиза."
            ) from error
        self._print_release_diagnostics(release)
        return release

    def download_archive_parts(
        self,
        release: ReleaseInfo,
        destination_directory: Path,
        progress_callback: ProgressCallback,
        is_cancelled: CancellationCallback = lambda: False,
    ) -> Path:
        self._require_configuration()
        parts = release.archive_parts
        if not parts:
            raise GitHubReleaseError(
                "В последнем релизе нет частей многотомного архива."
            )
        destination = destination_directory.expanduser().resolve()
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise GitHubReleaseError(
                f"Не удалось создать каталог загрузки: {destination}"
            ) from error

        total_bytes = sum(asset.size for asset in parts)
        completed_bytes = 0
        for index, asset in enumerate(parts, start=1):
            if is_cancelled():
                raise GitHubReleaseError("Загрузка отменена.")
            safe_asset_name = Path(asset.name).name
            if safe_asset_name in {"", ".", ".."}:
                raise GitHubReleaseError("GitHub вернул недопустимое имя файла.")
            final_path = (destination / safe_asset_name).resolve()
            partial_path = (destination / f"{safe_asset_name}.part").resolve()
            try:
                final_path.relative_to(destination)
                partial_path.relative_to(destination)
            except ValueError as error:
                raise GitHubReleaseError(
                    "GitHub вернул небезопасное имя файла."
                ) from error
            if final_path.is_file() and final_path.stat().st_size == asset.size:
                completed_bytes += asset.size
                progress_callback(
                    DownloadProgress(
                        safe_asset_name,
                        index,
                        len(parts),
                        completed_bytes,
                        total_bytes,
                        0.0,
                    )
                )
                continue
            try:
                final_path.unlink(missing_ok=True)
                partial_path.unlink(missing_ok=True)
            except OSError as error:
                raise GitHubReleaseError(
                    f"Не удалось подготовить файл для загрузки: {final_path}"
                ) from error

            last_error: Exception | None = None
            for attempt in range(1, 4):
                retry_status = "" if attempt == 1 else f"Повтор {attempt}/3"
                try:
                    self._download_asset(
                        asset,
                        partial_path,
                        index,
                        len(parts),
                        completed_bytes,
                        total_bytes,
                        retry_status,
                        progress_callback,
                        is_cancelled,
                    )
                    if partial_path.stat().st_size != asset.size:
                        raise GitHubReleaseError(
                            f"Файл {safe_asset_name} загружен не полностью."
                        )
                    partial_path.replace(final_path)
                    completed_bytes += asset.size
                    break
                except (GitHubReleaseError, OSError, requests.RequestException) as error:
                    last_error = error
                    partial_path.unlink(missing_ok=True)
                    if attempt < 3:
                        progress_callback(
                            DownloadProgress(
                                safe_asset_name,
                                index,
                                len(parts),
                                completed_bytes,
                                total_bytes,
                                0.0,
                                f"Повтор {attempt + 1}/3",
                            )
                        )
            else:
                if isinstance(last_error, GitHubReleaseError):
                    raise last_error
                raise GitHubReleaseError(
                    f"Не удалось загрузить файл {safe_asset_name}."
                ) from last_error
        return destination

    def _download_asset(
        self,
        asset: ReleaseAsset,
        partial_path: Path,
        file_index: int,
        file_count: int,
        completed_bytes: int,
        total_bytes: int,
        retry_status: str,
        progress_callback: ProgressCallback,
        is_cancelled: CancellationCallback,
    ) -> None:
        try:
            response = self._session.get(
                asset.api_url,
                headers=self._asset_headers(),
                stream=True,
                allow_redirects=True,
                timeout=(self._config.connect_timeout, self._config.read_timeout),
            )
        except requests.Timeout as error:
            raise GitHubReleaseError(
                "GitHub не ответил вовремя. Повторите попытку."
            ) from error
        self._raise_for_status(response)
        started = time.monotonic()
        received = 0
        try:
            with response, partial_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if is_cancelled():
                        raise GitHubReleaseError("Загрузка отменена.")
                    if not chunk:
                        continue
                    output.write(chunk)
                    received += len(chunk)
                    elapsed = max(time.monotonic() - started, 0.001)
                    progress_callback(
                        DownloadProgress(
                            asset.name,
                            file_index,
                            file_count,
                            completed_bytes + received,
                            total_bytes,
                            received / elapsed,
                            retry_status,
                        )
                    )
        except OSError as error:
            raise GitHubReleaseError(
                f"Не удалось записать файл: {partial_path}"
            ) from error

    def _require_configuration(self) -> None:
        if self._config.repository != "ErrorsLab32/Not-ME":
            raise GitHubReleaseError("Invalid playtest repository configuration.")
        if not self._config.token:
            raise GitHubReleaseError(
                "Не указан токен доступа к GitHub. Добавьте GITHUB_TOKEN в файл .env"
            )
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self._config.repository):
            raise GitHubReleaseError("Некорректно задан GITHUB_REPOSITORY в файле .env.")

    def _json_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": self.USER_AGENT,
        }

    def _asset_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.token}",
            "Accept": "application/octet-stream",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": self.USER_AGENT,
        }

    @staticmethod
    def _parse_asset(data: object) -> ReleaseAsset:
        if not isinstance(data, dict):
            raise TypeError("asset is not an object")
        size = data["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("invalid asset size")
        return ReleaseAsset(
            asset_id=int(data["id"]),
            name=str(data["name"]),
            size=size,
            content_type=str(data.get("content_type") or "application/octet-stream"),
            api_url=str(data["url"]),
            digest=str(data["digest"]) if data.get("digest") else None,
        )

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.status_code in (401, 403):
            raise GitHubReleaseError("Access to the playtest repository was denied.", response.status_code)
        if response.status_code == 401:
            raise GitHubReleaseError("Токен GitHub недействителен.")
        if response.status_code == 403:
            raise GitHubReleaseError(
                "Недостаточно прав для доступа к репозиторию или превышен лимит GitHub API."
            )
        if response.status_code == 404:
            raise GitHubReleaseError(
                "Репозиторий или опубликованный релиз не найден."
            )
        if response.status_code >= 400:
            raise GitHubReleaseError(
                f"GitHub вернул ошибку HTTP {response.status_code}."
            )

    @staticmethod
    def _print_release_diagnostics(release: ReleaseInfo) -> None:
        print(f"HTTP status: {release.http_status}")
        print(f"tag_name: {release.tag_name}")
        print(f"release: {release.name}")
        for asset in release.assets:
            print(f"asset: {asset.name} | {asset.size}")
