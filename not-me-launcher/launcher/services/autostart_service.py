from pathlib import Path
import os
import sys


class AutostartService:
    VALUE_NAME = "NotMeLauncher"
    KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    @staticmethod
    def command(entrypoint: Path | None = None) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}" --background'
        entrypoint = entrypoint or Path(sys.argv[0]).resolve()
        interpreter = Path(sys.executable).resolve()
        pythonw = interpreter.with_name("pythonw.exe")
        if pythonw.is_file():
            interpreter = pythonw
        return f'"{interpreter}" "{entrypoint}" --background'

    def apply(self, enabled: bool, entrypoint: Path | None = None) -> str | None:
        if os.name != "nt":
            return None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, self.VALUE_NAME, 0, winreg.REG_SZ, self.command(entrypoint))
                else:
                    try:
                        winreg.DeleteValue(key, self.VALUE_NAME)
                    except FileNotFoundError:
                        pass
        except (OSError, ImportError, AttributeError) as error:
            return f"Не удалось обновить автозапуск Windows: {error}"
        return None
