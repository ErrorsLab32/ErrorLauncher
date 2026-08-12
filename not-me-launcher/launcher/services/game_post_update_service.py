import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QProcess


LogCallback = Callable[[str], None]


class GamePostUpdateService:
    BAT_NAME = "Start_With_Test_Settings.bat"

    def __init__(self, log: LogCallback) -> None:
        self._log = log
        self._completed: set[tuple[str, Path]] = set()

    def run_after_update(self, version: str, executable: Path) -> None:
        executable = executable.expanduser().resolve()
        completion = (version, executable)
        if completion in self._completed:
            self._log(
                f"post-update bat skipped reason=already-completed version={version} "
                f"game_exe_path={executable}"
            )
            return
        self._completed.add(completion)
        self._log(f"post-update game_exe_path={executable}")

        batch_file = executable.parent / self.BAT_NAME
        if not batch_file.is_file():
            self._log(f"post-update bat missing bat_path={batch_file}")
            return
        self._log(f"post-update bat_path={batch_file}")
        if os.name != "nt":
            self._log("post-update bat skipped reason=non-windows")
            return
        try:
            started, process_id = QProcess.startDetached(
                "cmd.exe",
                ["/c", str(batch_file)],
                str(executable.parent),
            )
        except (OSError, TypeError) as error:
            self._log(f"post-update bat start failed bat_path={batch_file} error={error!r}")
            return
        self._log(
            f"post-update bat start bat_path={batch_file} started={started} "
            f"pid={int(process_id) if started else None}"
        )
