from pathlib import Path

from PySide6.QtCore import QProcess


class GameLaunchError(Exception):
    pass


class GameProcessService:
    @staticmethod
    def launch(executable: Path) -> int:
        executable = executable.expanduser().resolve()
        if not executable.is_file():
            raise GameLaunchError(
                "Не удалось запустить игру. Файл игры отсутствует или недоступен."
            )
        try:
            started, process_id = QProcess.startDetached(
                str(executable),
                [],
                str(executable.parent),
            )
        except (OSError, TypeError) as error:
            raise GameLaunchError(
                "Не удалось запустить игру. Файл игры отсутствует или недоступен."
            ) from error
        if not started:
            raise GameLaunchError(
                "Не удалось запустить игру. Файл игры отсутствует или недоступен."
            )
        return int(process_id)
