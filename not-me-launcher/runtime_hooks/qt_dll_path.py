"""Make PySide6's bundled Qt DLL directory explicit for the Windows loader."""

import os
from pathlib import Path
import sys


if sys.platform == "win32":
    runtime_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    for bundled_dll_directory in (runtime_root, runtime_root / "PySide6", runtime_root / "shiboken6"):
        if bundled_dll_directory.is_dir():
            os.add_dll_directory(str(bundled_dll_directory))
