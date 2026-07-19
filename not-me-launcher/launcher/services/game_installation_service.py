from dataclasses import dataclass
from datetime import datetime
import locale
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable, Iterable

from launcher.config import PROJECT_ROOT
from launcher.installation_preferences import (
    InstallationPathError,
    InstallationPreferences,
    safe_tag_name,
)
from launcher.models.release_info import ReleaseAsset, ReleaseInfo


StageCallback = Callable[[str], None]


class GameInstallationError(Exception):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class InstallationResult:
    installed_version: str
    executable_path: Path


class GameInstallationService:
    EXTRACTOR_NOT_FOUND = (
        "Не найден компонент распаковки 7-Zip. "
        "Установка сборки невозможна."
    )
    INCOMPLETE_DOWNLOAD = (
        "Файлы сборки загружены не полностью. Повторите загрузку."
    )

    def __init__(self, preferences: InstallationPreferences) -> None:
        self._preferences = preferences
        self._log_path = preferences.state_path.parent / "logs" / "installation.log"

    def download_is_complete(self, release: ReleaseInfo) -> bool:
        try:
            directory = self._preferences.release_download_directory(release.tag_name)
        except InstallationPathError:
            return False
        parts = release.archive_parts
        if not parts:
            return False
        return all(self._asset_is_complete(directory, asset) for asset in parts)

    def install(
        self,
        release: ReleaseInfo,
        stage_callback: StageCallback,
    ) -> InstallationResult:
        install_path = self._preferences.install_path
        if install_path is None:
            raise GameInstallationError("Папка установки не выбрана.")
        install_path = install_path.resolve()
        service_root = (install_path / ".errorlabs-playtest").resolve()
        download_directory = self._preferences.release_download_directory(
            release.tag_name
        )
        staging_directory = (
            service_root / "staging" / safe_tag_name(release.tag_name)
        ).resolve()
        backup_directory = (service_root / "backup" / "game").resolve()
        game_directory = (install_path / "game").resolve()
        for path in (download_directory, staging_directory, backup_directory):
            self._require_inside(path, service_root)
        self._require_inside(game_directory, install_path)

        archive_assets = release.archive_parts
        self._verify_downloads(download_directory, archive_assets)
        first_volume = self.detect_first_volume(
            download_directory / asset.name for asset in archive_assets
        )
        extractor = self.find_extractor()
        if extractor is None:
            raise GameInstallationError(self.EXTRACTOR_NOT_FOUND)

        self._log(
            f"install start state=Installing version={release.tag_name} "
            f"first_volume={first_volume.name} extractor={extractor}"
        )
        stage_callback("Установка сборки")
        self._remove_stale_staging(staging_directory)
        staging_directory.mkdir(parents=True, exist_ok=True)
        self._extract(extractor, first_volume, staging_directory)

        game_root = self._select_game_root(staging_directory)
        executable = self._find_game_executable(game_root)
        relative_executable = executable.relative_to(game_root)
        self._log(f"selected executable={relative_executable}")

        stage_callback("Завершение установки")
        installed_relative = Path("game") / relative_executable
        self._replace_game(
            game_directory,
            game_root,
            backup_directory,
            release.tag_name,
            installed_relative,
        )

        self._cleanup_after_success(
            download_directory,
            staging_directory,
            backup_directory,
            archive_assets,
        )
        self._log(
            f"install success state=ReadyToPlay version={release.tag_name} "
            f"executable={installed_relative}"
        )
        return InstallationResult(release.tag_name, installed_relative)

    @staticmethod
    def detect_first_volume(files: Iterable[Path]) -> Path:
        candidates = sorted(
            (Path(path) for path in files),
            key=lambda path: path.name.lower(),
        )
        checks = (
            lambda name: name.endswith(".7z.001"),
            lambda name: name.endswith(".zip.001"),
            lambda name: re.search(r"\.part0*1\.rar$", name) is not None,
            lambda name: name.endswith(".rar"),
            lambda name: name.endswith(".7z"),
            lambda name: name.endswith(".zip"),
        )
        for check in checks:
            matching = [path for path in candidates if check(path.name.lower())]
            if len(matching) == 1:
                return matching[0]
            if len(matching) > 1:
                names = ", ".join(path.name for path in matching)
                raise GameInstallationError(
                    f"Не удалось однозначно определить первый том архива: {names}"
                )
        names = ", ".join(path.name for path in candidates) or "файлы отсутствуют"
        raise GameInstallationError(
            f"Не удалось определить формат архива. Найдены файлы: {names}"
        )

    @staticmethod
    def find_extractor() -> Path | None:
        project_candidates = (
            PROJECT_ROOT / "tools" / "7zip" / "7za.exe",
            PROJECT_ROOT / "tools" / "7zip" / "7z.exe",
        )
        for candidate in project_candidates:
            if candidate.is_file():
                return candidate.resolve()
        from_path = shutil.which("7z.exe")
        if from_path:
            return Path(from_path).resolve()
        for candidate in (
            Path("C:/Program Files/7-Zip/7z.exe"),
            Path("C:/Program Files (x86)/7-Zip/7z.exe"),
        ):
            if candidate.is_file():
                return candidate.resolve()
        return None

    def _verify_downloads(
        self,
        directory: Path,
        assets: tuple[ReleaseAsset, ...],
    ) -> None:
        if not assets or not all(
            self._asset_is_complete(directory, asset) for asset in assets
        ):
            raise GameInstallationError(self.INCOMPLETE_DOWNLOAD)

    @staticmethod
    def _asset_is_complete(directory: Path, asset: ReleaseAsset) -> bool:
        safe_name = Path(asset.name).name
        if safe_name != asset.name:
            return False
        file_path = directory / safe_name
        try:
            return file_path.is_file() and file_path.stat().st_size == asset.size
        except OSError:
            return False

    def _remove_stale_staging(self, staging_directory: Path) -> None:
        if staging_directory.exists():
            try:
                shutil.rmtree(staging_directory)
            except OSError as error:
                self._log(f"staging cleanup failed error={error!r}")
                raise GameInstallationError(
                    "Не удалось подготовить временную папку установки."
                ) from error

    def _extract(
        self,
        extractor: Path,
        first_volume: Path,
        staging_directory: Path,
    ) -> None:
        arguments = [
            str(extractor),
            "x",
            str(first_volume),
            f"-o{staging_directory}",
            "-y",
        ]
        try:
            result = subprocess.run(
                arguments,
                shell=False,
                capture_output=True,
                timeout=60 * 60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            self._log(f"extractor start/timeout failure error={error!r}")
            raise GameInstallationError(
                "Не удалось распаковать файлы сборки"
            ) from error
        stdout = self._decode_output(result.stdout)
        stderr = self._decode_output(result.stderr)
        self._log(
            f"extractor exit_code={result.returncode}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
        if result.returncode != 0:
            raise GameInstallationError("Не удалось распаковать файлы сборки")

    @staticmethod
    def _decode_output(output: bytes) -> str:
        for encoding in (locale.getpreferredencoding(False), "utf-8", "cp866"):
            try:
                return output.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return output.decode("utf-8", errors="replace")

    @staticmethod
    def _select_game_root(staging_directory: Path) -> Path:
        children = list(staging_directory.iterdir())
        directories = [path for path in children if path.is_dir()]
        files = [path for path in children if path.is_file()]
        if len(directories) == 1 and not files:
            return directories[0]
        return staging_directory

    def _find_game_executable(self, game_root: Path) -> Path:
        excluded_names = {
            "crashreportclient.exe",
            "ueprereqsetup_x64.exe",
            "unrealcefsubprocess.exe",
            "epicwebhelper.exe",
        }
        candidates = [
            path
            for path in game_root.rglob("*.exe")
            if path.name.lower() not in excluded_names
            and "uninstall" not in path.name.lower()
            and "setup" not in path.name.lower()
        ]
        if not candidates:
            raise GameInstallationError(
                "Не удалось найти исполняемый файл игры в распакованной сборке."
            )

        root_candidates = [path for path in candidates if path.parent == game_root]
        selected = self._select_unambiguous(root_candidates)
        if selected is not None:
            return selected

        named_candidates = [
            path
            for path in candidates
            if re.sub(r"[^a-z0-9]", "", path.stem.lower()).startswith("notme")
        ]
        selected = self._select_unambiguous(named_candidates)
        if selected is not None:
            return selected

        if not root_candidates and len(candidates) == 1:
            return candidates[0]

        ambiguous = root_candidates or named_candidates or candidates
        relative_paths = [str(path.relative_to(game_root)) for path in ambiguous]
        print("Неоднозначные исполняемые файлы:")
        for relative_path in relative_paths:
            print(relative_path)
        self._log("ambiguous executables=" + " | ".join(relative_paths))
        raise GameInstallationError(
            "Не удалось однозначно определить исполняемый файл игры."
        )

    @staticmethod
    def _select_unambiguous(candidates: list[Path]) -> Path | None:
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _replace_game(
        self,
        game_directory: Path,
        prepared_game_root: Path,
        backup_directory: Path,
        version: str,
        installed_relative: Path,
    ) -> None:
        backup_parent = backup_directory.parent
        backup_parent.mkdir(parents=True, exist_ok=True)
        replacement_marker = backup_parent / ".replacement-version"
        if backup_directory.exists():
            marker_version = self._read_marker(replacement_marker)
            if (
                game_directory.exists()
                and marker_version is not None
                and self._versions_equal(
                    marker_version,
                    self._preferences.installed_version or "",
                )
            ):
                shutil.rmtree(backup_directory)
                replacement_marker.unlink(missing_ok=True)
            else:
                try:
                    if game_directory.exists():
                        shutil.rmtree(game_directory)
                    backup_directory.replace(game_directory)
                    replacement_marker.unlink(missing_ok=True)
                except OSError as error:
                    self._log(f"interrupted replacement recovery failed error={error!r}")
                    raise GameInstallationError(
                        "Не удалось восстановить предыдущую установку."
                    ) from error
                raise GameInstallationError(
                    "Восстановлена предыдущая установка после незавершённого обновления."
                )
        elif replacement_marker.exists():
            replacement_marker.unlink(missing_ok=True)

        old_game_was_moved = False
        new_game_was_placed = False
        try:
            if game_directory.exists():
                replacement_marker.write_text(version, encoding="utf-8")
                game_directory.replace(backup_directory)
                old_game_was_moved = True
            prepared_game_root.replace(game_directory)
            new_game_was_placed = True
            final_executable = (
                self._preferences.install_path / installed_relative
                if self._preferences.install_path is not None
                else None
            )
            if final_executable is None or not final_executable.is_file():
                raise OSError("expected executable is missing after replacement")
            self._preferences.mark_installation_complete(version, installed_relative)
        except (OSError, InstallationPathError) as error:
            self._log(f"replacement failure error={error!r}")
            rollback_error: OSError | None = None
            try:
                if new_game_was_placed and game_directory.exists():
                    shutil.rmtree(game_directory)
                if old_game_was_moved and backup_directory.exists():
                    backup_directory.replace(game_directory)
                replacement_marker.unlink(missing_ok=True)
            except OSError as caught:
                rollback_error = caught
                self._log(f"rollback failure error={caught!r}")
            if rollback_error is not None:
                raise GameInstallationError(
                    "Не удалось заменить установленную версию и восстановить предыдущую."
                ) from rollback_error
            raise GameInstallationError(
                "Не удалось заменить установленную версию игры."
            ) from error

    def _cleanup_after_success(
        self,
        download_directory: Path,
        staging_directory: Path,
        backup_directory: Path,
        assets: tuple[ReleaseAsset, ...],
    ) -> None:
        cleanup_errors: list[str] = []
        targets = [download_directory / Path(asset.name).name for asset in assets]
        targets.extend(download_directory / f"{Path(asset.name).name}.part" for asset in assets)
        if download_directory.is_dir():
            targets.extend(download_directory.glob("*.part"))
        for target in targets:
            try:
                target.unlink(missing_ok=True)
            except OSError as error:
                cleanup_errors.append(f"{target}: {error!r}")
        for directory in (backup_directory, staging_directory):
            if directory.exists():
                try:
                    shutil.rmtree(directory)
                except OSError as error:
                    cleanup_errors.append(f"{directory}: {error!r}")
        replacement_marker = backup_directory.parent / ".replacement-version"
        try:
            replacement_marker.unlink(missing_ok=True)
        except OSError as error:
            cleanup_errors.append(f"{replacement_marker}: {error!r}")
        try:
            download_directory.rmdir()
        except OSError:
            pass
        if cleanup_errors:
            self._log("cleanup warnings=" + " | ".join(cleanup_errors))

    @staticmethod
    def _require_inside(path: Path, parent: Path) -> None:
        try:
            path.relative_to(parent)
        except ValueError as error:
            raise GameInstallationError("Некорректный путь установки.") from error

    def _log(self, message: str) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass

    @staticmethod
    def _read_marker(marker: Path) -> str | None:
        try:
            value = marker.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return value or None

    @staticmethod
    def _versions_equal(first: str, second: str) -> bool:
        def normalize(value: str) -> str:
            normalized = value.strip().lower()
            if normalized.startswith("v"):
                normalized = normalized[1:]
            return normalized.lstrip("._-")

        return normalize(first) == normalize(second)
