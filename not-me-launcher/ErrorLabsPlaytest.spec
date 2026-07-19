# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH)
datas = [
    (
        str(project_root / "launcher" / "resources" / "styles.qss"),
        "launcher/resources",
    ),
]

launcher_analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
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
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
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
