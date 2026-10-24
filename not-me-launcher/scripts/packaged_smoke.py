"""Exercise a Windows packaged install, Run value, shortcut, and real updater.

Run against a smoke installer compiled with a distinct MyAppId. The report
explicitly excludes a real Windows reboot, which requires a separate machine.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import winreg
import zipfile


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    print(f"PASS: {message}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    require(not root.exists(), "fresh dedicated smoke directory")
    root.mkdir(parents=True)
    local = root / "LocalAppData"
    install = local / "Programs" / "ErrorLabs Playtest"
    exe = install / "ErrorLabsPlaytest.exe"
    data = local / "ErrorLabs" / "ErrorLabs Playtest"
    temp = root / "temp"
    temp.mkdir()
    env = os.environ.copy()
    env.update(LOCALAPPDATA=str(local), ERRORLABS_LOCAL_DATA_DIR=str(data),
               ERRORLABS_SMOKE_TEST="1", TEMP=str(temp), TMP=str(temp))
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_ALL_ACCESS)
    try:
        previous = winreg.QueryValueEx(key, "NotMeLauncher")
    except FileNotFoundError:
        previous = None
    processes = []
    report = {"version": args.version, "root": str(root), "reboot": "NOT TESTED"}
    try:
        subprocess.run([str(args.setup.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                        "/NORESTART", "/NOICONS", f"/DIR={install}",
                        f"/LOG={root / 'installer.log'}"], env=env, check=True, timeout=120)
        require(exe.is_file() and not exe.is_relative_to(temp), "installer writes stable executable")
        first = subprocess.Popen([str(exe), "--background"], cwd=install, env=env)
        processes.append(first)
        # Startup includes Qt loading and shortcut inspection. A hosted runner
        # may take longer than three seconds; wait for the actual readiness
        # condition rather than querying Run before startup has registered it.
        command = None
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and first.poll() is None:
            try:
                command = winreg.QueryValueEx(key, "NotMeLauncher")[0]
            except FileNotFoundError:
                pass
            if command == f'"{exe}" --background':
                break
            time.sleep(0.2)
        require(first.poll() is None, "packaged Qt launcher remains running")
        require(command == f'"{exe}" --background', "autostart targets stable exe with --background")
        shortcut = root / "ErrorLabs Playtest.lnk"
        ps = "$s=New-Object -ComObject WScript.Shell; $l=$s.CreateShortcut($env:SMOKE_LINK); $l.TargetPath=$env:SMOKE_EXE; $l.WorkingDirectory=$env:SMOKE_INSTALL; $l.Save(); $s.Run(('\"'+$env:SMOKE_LINK+'\"'),0,$false)"
        link_env = env | {"SMOKE_LINK": str(shortcut), "SMOKE_EXE": str(exe), "SMOKE_INSTALL": str(install)}
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], env=link_env, check=True, timeout=20)
        require(first.wait(timeout=25) == 0, "shortcut activation and graceful launcher shutdown")
        package = root / "update.zip"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in args.payload.resolve().rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(args.payload.resolve()).as_posix())
        old_uninstall = {p.name: p.read_bytes() for p in install.glob("unins*.*") if p.is_file()}
        launcher = subprocess.Popen([str(exe), "--background"], cwd=install, env=env)
        processes.append(launcher)
        runtime = data / "updater-runtime" / args.version
        runtime.mkdir(parents=True)
        updater = runtime / "ErrorLabsUpdater.exe"
        shutil.copy2(install / updater.name, updater)
        update = subprocess.Popen([str(updater), "--package", str(package), "--target", str(install),
                                   "--entrypoint", exe.name, "--pid", str(launcher.pid),
                                   "--version", args.version], cwd=runtime, env=env)
        processes.append(update)
        time.sleep(3)
        require(launcher.poll() is None, "updater liveness probe leaves launcher alive")
        require(launcher.wait(timeout=25) == 0, "updater waits for graceful main-process exit")
        require(update.wait(timeout=75) == 0, "packaged updater completes")
        updater_log = (data / "logs" / "updater.log").read_text(encoding="utf-8")
        require("update completed successfully" in updater_log, "new launcher confirms update health")
        require(all((install / name).read_bytes() == content for name, content in old_uninstall.items()),
                "self-update preserves Inno uninstall metadata")
        work = install.parent / ".errorlabs-updater"
        require(not list(work.glob("staging-*")) and not list(work.glob("backup-*")), "staging and backup removed")
        time.sleep(14)  # let the restarted smoke launcher close and release runtime DLLs
        shutil.rmtree(temp)
        temp.mkdir()
        final = subprocess.Popen(command, cwd=install, env=env)
        processes.append(final)
        require(final.wait(timeout=25) == 0, "autostart command works after owned TEMP cleanup")
        require(not list(temp.rglob("ErrorLabsPlaytest.exe")), "no launcher executable left in TEMP")
        report["result"] = "PASS (reboot pending)"
        report.update(executable=str(exe), install_directory=str(install),
                      autostart_target=command, shortcut=str(shortcut),
                      staging_root=str(work), temp_directory=str(temp))
    except Exception as error:
        report.update(result="FAIL", error=repr(error))
        raise
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if previous is None:
            try:
                winreg.DeleteValue(key, "NotMeLauncher")
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, "NotMeLauncher", 0, previous[1], previous[0])
        key.Close()
        (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
