from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import subprocess
import time
import traceback
import zipfile

from PySide6.QtCore import QLockFile


StatusCallback = Callable[[str, bool], None]


class UpdateEngineError(Exception):
    pass


@dataclass(frozen=True)
class UpdateRequest:
    package: Path
    target: Path
    entrypoint: Path
    launcher_pid: int
    version: str


class UpdateEngine:
    def __init__(
        self,
        request: UpdateRequest,
        local_data: Path,
        wait_timeout: float = 60.0,
        health_timeout: float = 45.0,
        process_launcher: Callable[[Path, Path], subprocess.Popen] | None = None,
    ) -> None:
        self.request = request
        self.local_data = local_data.expanduser().resolve()
        self.wait_timeout = wait_timeout
        self.health_timeout = health_timeout
        self._process_launcher = process_launcher or self._launch_process
        self.log_path = self.local_data / "logs" / "updater.log"
        work_root = request.target.resolve().parent / ".errorlabs-updater"
        self.staging = work_root / f"staging-{request.version}"
        self.backup = work_root / f"backup-{request.version}"
        self.health_marker = (
            self.local_data / "update-health" / f"{request.version}.ok"
        )

    def apply(self, status_callback: StatusCallback) -> None:
        request = self.request
        package = request.package.expanduser().resolve()
        target = request.target.expanduser().resolve()
        entrypoint = self._validate_entrypoint(request.entrypoint)
        if not package.is_file():
            raise UpdateEngineError("Пакет обновления не найден.")
        if not target.is_dir():
            raise UpdateEngineError("Папка установленного лаунчера не найдена.")

        self._log(
            f"update start version={request.version} target={target} package={package.name}"
        )
        status_callback("Ожидание завершения лаунчера", True)
        if not self._wait_for_process_exit(request.launcher_pid):
            raise UpdateEngineError("Лаунчер не завершился за отведённое время.")
        self._wait_for_instance_lock()

        status_callback("Установка обновления", True)
        self._check_target_writable(target)
        self._prepare_staging(package, entrypoint)
        self.health_marker.unlink(missing_ok=True)
        if self.backup.exists():
            raise UpdateEngineError(
                "Обнаружена незавершённая предыдущая попытка обновления."
            )

        moved_old = False
        moved_new = False
        new_process: subprocess.Popen | None = None
        try:
            target.replace(self.backup)
            moved_old = True
            self.staging.replace(target)
            moved_new = True
            installed_entrypoint = (target / entrypoint).resolve()
            self._require_inside(installed_entrypoint, target)
            if not installed_entrypoint.is_file():
                raise UpdateEngineError(
                    "Новая версия не содержит исполняемый файл лаунчера."
                )

            status_callback("Проверка новой версии", True)
            new_process = self._process_launcher(
                installed_entrypoint,
                installed_entrypoint.parent,
            )
            if not self._wait_for_health_marker(new_process):
                raise UpdateEngineError(
                    "Новая версия лаунчера не подтвердила успешный запуск."
                )

            status_callback("Перезапуск", True)
            shutil.rmtree(self.backup, ignore_errors=True)
            self._log("update completed successfully")
        except Exception as error:
            self._log(
                f"update failed error={error!r}\n{traceback.format_exc()}"
            )
            if new_process is not None and new_process.poll() is None:
                try:
                    new_process.terminate()
                    new_process.wait(timeout=5)
                except (OSError, subprocess.SubprocessError):
                    pass
            rollback_error = self._rollback(target, moved_old, moved_new, entrypoint)
            if rollback_error is not None:
                self._log(f"rollback failed error={rollback_error!r}")
                raise UpdateEngineError(
                    "Обновление не установлено, восстановление предыдущей версии не удалось."
                ) from rollback_error
            if isinstance(error, UpdateEngineError):
                raise
            raise UpdateEngineError("Не удалось установить обновление лаунчера.") from error
        finally:
            if self.staging.exists():
                shutil.rmtree(self.staging, ignore_errors=True)

    def _prepare_staging(self, package: Path, entrypoint: Path) -> None:
        if self.staging.exists():
            shutil.rmtree(self.staging)
        self.staging.mkdir(parents=True)
        try:
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    destination = self._safe_zip_destination(info)
                    if info.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
        except (OSError, zipfile.BadZipFile) as error:
            raise UpdateEngineError("Пакет обновления повреждён.") from error
        expected = (self.staging / entrypoint).resolve()
        self._require_inside(expected, self.staging)
        if not expected.is_file():
            raise UpdateEngineError(
                "Пакет обновления не содержит исполняемый файл лаунчера."
            )

    def _safe_zip_destination(self, info: zipfile.ZipInfo) -> Path:
        name = info.filename.replace("\\", "/")
        posix = PurePosixPath(name)
        windows = PureWindowsPath(name)
        mode = info.external_attr >> 16
        if (
            posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or stat.S_ISLNK(mode)
        ):
            raise UpdateEngineError("ZIP-пакет содержит небезопасный путь.")
        destination = (self.staging / Path(*posix.parts)).resolve()
        self._require_inside(destination, self.staging)
        return destination

    def _rollback(
        self,
        target: Path,
        moved_old: bool,
        moved_new: bool,
        entrypoint: Path,
    ) -> OSError | None:
        try:
            if moved_new and target.exists():
                shutil.rmtree(target)
            if moved_old and self.backup.exists():
                self.backup.replace(target)
                old_entrypoint = (target / entrypoint).resolve()
                if old_entrypoint.is_file():
                    self._process_launcher(old_entrypoint, old_entrypoint.parent)
            return None
        except OSError as error:
            return error

    def _wait_for_process_exit(self, process_id: int) -> bool:
        deadline = time.monotonic() + self.wait_timeout
        while time.monotonic() < deadline:
            if not self._process_exists(process_id):
                return True
            time.sleep(0.2)
        return not self._process_exists(process_id)

    def _wait_for_health_marker(self, process: subprocess.Popen) -> bool:
        deadline = time.monotonic() + self.health_timeout
        while time.monotonic() < deadline:
            if self.health_marker.is_file():
                return True
            if process.poll() is not None:
                return False
            time.sleep(0.25)
        return self.health_marker.is_file()

    def _wait_for_instance_lock(self) -> None:
        lock = QLockFile(str(self.local_data / "errorlabs-playtest.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(int(self.wait_timeout * 1000)):
            raise UpdateEngineError(
                "Не удалось дождаться освобождения блокировки лаунчера."
            )
        lock.unlock()

    @staticmethod
    def _process_exists(process_id: int) -> bool:
        if process_id <= 0:
            return False
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _launch_process(executable: Path, working_directory: Path) -> subprocess.Popen:
        return subprocess.Popen(
            [str(executable)],
            cwd=str(working_directory),
            shell=False,
            close_fds=True,
        )

    @staticmethod
    def _validate_entrypoint(entrypoint: Path) -> Path:
        text = str(entrypoint).replace("\\", "/")
        posix = PurePosixPath(text)
        windows = PureWindowsPath(text)
        if (
            posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or not posix.parts
        ):
            raise UpdateEngineError("Некорректный путь запуска новой версии.")
        return Path(*posix.parts)

    @staticmethod
    def _check_target_writable(target: Path) -> None:
        probe = target / ".errorlabs-updater-write-test"
        try:
            probe.write_bytes(b"ok")
            probe.unlink()
        except OSError as error:
            probe.unlink(missing_ok=True)
            raise UpdateEngineError(
                "Нет доступа для записи в папку лаунчера."
            ) from error

    @staticmethod
    def _require_inside(path: Path, parent: Path) -> None:
        try:
            path.relative_to(parent.resolve())
        except ValueError as error:
            raise UpdateEngineError("Обнаружен небезопасный путь обновления.") from error

    def _log(self, message: str) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as output:
                output.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass
