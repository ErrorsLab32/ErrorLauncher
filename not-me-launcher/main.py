from datetime import datetime
import os
from pathlib import Path
import sys
import traceback


def _startup_crash_log_path() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    root = Path(local_app_data) if local_app_data else Path.cwd()
    return root / "ErrorLabs" / "ErrorLabs Playtest" / "logs" / "startup-crash.log"


def _write_startup_crash(error: BaseException) -> None:
    try:
        path = _startup_crash_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] startup failure\n")
            output.write(f"executable: {sys.executable}\n")
            output.write("".join(traceback.format_exception(error)))
            output.write("\n")
    except OSError:
        pass


def main() -> int:
    try:
        from launcher.app import run

        return run()
    except BaseException as error:
        _write_startup_crash(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
