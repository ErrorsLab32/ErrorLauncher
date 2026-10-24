# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH)
datas = [
    (
        str(project_root / "launcher" / "resources" / "styles.qss"),
        "launcher/resources",
    ),
    (
        str(project_root / "launcher" / "resources" / "launcher.svg"),
        "launcher/resources",
    ),
]


def without_host_icu(entries):
    return [
        entry
        for entry in entries
        if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}
    ]

launcher_analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["shiboken6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtNetwork", "PySide6.QtPdf", "PySide6.QtSvg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "runtime_hooks" / "qt_dll_path.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
launcher_analysis.binaries = without_host_icu(launcher_analysis.binaries)
launcher_pyz = PYZ(launcher_analysis.pure)
launcher_exe = EXE(
    launcher_pyz,
    launcher_analysis.scripts,
    [],
    exclude_binaries=True,
    name="ErrorLabsPlaytest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    contents_directory="_internal",
)

updater_analysis = Analysis(
    [str(project_root / "updater" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=["shiboken6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtNetwork", "PySide6.QtPdf", "PySide6.QtSvg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "runtime_hooks" / "qt_dll_path.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
updater_analysis.binaries = without_host_icu(updater_analysis.binaries)
updater_pyz = PYZ(updater_analysis.pure)
updater_exe = EXE(
    updater_pyz,
    updater_analysis.scripts,
    updater_analysis.binaries,
    updater_analysis.datas,
    [],
    exclude_binaries=False,
    name="ErrorLabsUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    launcher_exe,
    updater_exe,
    launcher_analysis.binaries,
    launcher_analysis.datas,
    strip=False,
    upx=True,
    name="release",
)
