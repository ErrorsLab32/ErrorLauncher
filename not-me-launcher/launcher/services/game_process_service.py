from pathlib import Path

from PySide6.QtCore import QProcess

from launcher.services.graphics_settings_service import (
    GraphicsSettingsError,
    apply_graphics_preset,
)


class GameLaunchError(Exception):
    pass


class GameProcessService:
    @staticmethod
    def launch(executable: Path, graphics_preset: str = "epic") -> int:
        executable = executable.expanduser().resolve()
        if not executable.is_file():
            raise GameLaunchError(
                "Не удалось запустить игру. Файл игры отсутствует или недоступен."
            )
        try:
            apply_graphics_preset(graphics_preset)
        except GraphicsSettingsError as error:
            raise GameLaunchError(str(error)) from error
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
