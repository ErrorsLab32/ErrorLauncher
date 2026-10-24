# Windows launcher path fix (0.2.9)

## Cause and evidence

The launcher spec has used PyInstaller **onedir** since the packaging feature
was introduced. The launcher executable itself is not extracted to `_MEI*`.
`sys._MEIPASS` and `__file__` refer to its `_internal` resource directory.
Only the standalone updater is onefile; its unpack directory is temporary.

Inno Setup's default installation has always been
`%LOCALAPPDATA%\Programs\ErrorLabs Playtest`. There was no code that installed
the launcher to TEMP by default. However, the running executable's parent was
used as both the autostart authority and update target. Starting an extracted
update ZIP in TEMP therefore registered that copy and updated it in place.
Deleting TEMP then removed the executable Windows was configured to launch.
This is the D -> C failure mechanism, not a `_MEIPASS`/installed-exe mixup.

During the investigation, the host Run value and a live process pointed to
`%TEMP%\errorlauncher-smoke\installed-0.1.4\ErrorLabsPlaytest.exe`.
That path identifies an earlier smoke installation, not proof that the
production installer defaulted to TEMP. Its exact process and directory were
removed during the investigation. No claim is made that unrelated production
installations were inspected.

Two independent defects were uncovered while performing the packaged test:

* PyInstaller resolved an ICU dependency from the host Poppler PATH. The
  resulting `icuuc.dll` and `icudt78.dll` conflicted with Qt and caused WinError
  127 on QtCore import. The spec excludes them from both executables.
* The updater used `os.kill(pid, 0)` as a liveness probe. On Windows that calls
  TerminateProcess instead of performing the POSIX existence check. It is now
  a typed OpenProcess/WaitForSingleObject probe. A subprocess regression test
  verifies that probing leaves the child alive. Packaged updates now wait for
  graceful exit and can rename the installation successfully.

## Architecture

`launcher/runtime_paths.py` is the authority for the canonical install path.
Packaged startup from another directory delegates to that installed executable
or fails with a startup diagnostic when Setup has not been run. Inno uses the
same default and no longer reuses an obsolete prior installation directory.

Run points to the canonical executable with `--background`. The updater rejects
other installation targets. Resources and DLL search use `_MEIPASS` only for
bundled runtime loading. The updater runtime copy remains outside the directory
being replaced. Staging and backup are siblings of the installation, under
`%LOCALAPPDATA%\Programs\.errorlabs-updater`.

Updates wait for process exit, prepare and validate the extracted package, keep
the Inno uninstall metadata, swap into the canonical installation, start only
its installed entrypoint, wait for its health marker, and remove staging/backup.
Restarted executables get `PYINSTALLER_RESET_ENVIRONMENT=1`.

Startup diagnostics record the real executable, argv[0], cwd, __file__, TEMP,
_MEIPASS, install directory, registered Run value, inspected shortcut targets,
expected shortcut target, updater target, runtime directory and staging root.

## Verification

72 unit/regression tests pass. `scripts/packaged_smoke.py` runs a real Inno
installer with a separate smoke AppId, real packaged GUI processes, the Run
registry value, a Windows shortcut, and the standalone updater. It restores the
original Run value. It checks graceful exit, a successful replacement and
restart in the same directory, retained uninstall metadata, deleted staging and
backup, and launch using the Run command after clearing its dedicated TEMP.

The automated packaged test passed locally on Windows 11 for the corrected
0.2.9 payload, including installation and self-update. The release workflow now
runs it before publishing any tag or assets.
Each run saves `report.json`, installer and launcher/updater logs in its chosen
smoke root. Network download/hash validation remains covered by service tests;
the packaged test uses a local ZIP so it cannot fetch or publish another release.

A physical Windows reboot and clearing unrelated host TEMP files are not
performed by this script. The report explicitly marks reboot as not tested.
The user explicitly approved publication without a physical reboot after the
real Run-command check passed.

## Changed files

* `launcher/runtime_paths.py`, `main.py`: canonical paths, startup diagnostics,
  redirection from noninstalled copies.
* `launcher/app.py`: canonical backup cleanup and bounded smoke lifecycle.
* `launcher/services/autostart_service.py`: stable Run target and path checks.
* `launcher/services/single_instance_service.py`: 64-bit Windows handle types.
* `launcher/launcher_update_controller.py`, `updater/update_engine.py`,
  `updater/main.py`: stable update target, safe process wait, restart environment,
  uninstall metadata, and worker shutdown.
* `ErrorLabsPlaytest.spec`, `runtime_hooks/qt_dll_path.py`,
  `scripts/build_launcher.ps1`: Qt runtime packaging.
* `installer/ErrorLabsPlaytest.iss`: stable directory and isolated smoke AppId.
* `scripts/packaged_smoke.py`, `.github/workflows/publish-launcher.yml`: actual
  packaged verification and publication gate.
* `tests/test_runtime_paths.py`, `tests/test_autostart_service.py`,
  `tests/test_launcher_update_controller.py`, `tests/test_update_engine.py`,
  `tests/test_packaged_startup.py`:
  regression coverage.
* `launcher/version.py`: patch version 0.2.9.
