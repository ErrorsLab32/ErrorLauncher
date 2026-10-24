param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $PythonExecutable) {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $PythonExecutable = if (Test-Path -LiteralPath $venvPython) {
        $venvPython
    } else {
        "python"
    }
}

& $PythonExecutable -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed."
}

Push-Location $projectRoot
try {
    & $PythonExecutable -m PyInstaller `
        --noconfirm `
        --clean `
        "ErrorLabsPlaytest.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }
} finally {
    Pop-Location
}

$launcherExe = Join-Path $projectRoot "dist\release\ErrorLabsPlaytest.exe"
$updaterExe = Join-Path $projectRoot "dist\release\ErrorLabsUpdater.exe"

# PyInstaller resolves Qt's ICU imports against an unrelated Poppler/host ICU
# DLL when that DLL is present on the build machine. Qt 6.11 loads correctly
# without these optional ICU files; shipping the host copies causes WinError
# 127 in QtCore during packaged startup.
foreach ($foreignQtRuntimeFile in @("icuuc.dll", "icudt78.dll")) {
    $foreignPath = Join-Path $projectRoot "dist\release\_internal\$foreignQtRuntimeFile"
    if (Test-Path -LiteralPath $foreignPath -PathType Leaf) {
        Remove-Item -LiteralPath $foreignPath -Force
    }
}

if (-not (Test-Path -LiteralPath $launcherExe -PathType Leaf)) {
    throw "dist/release/ErrorLabsPlaytest.exe was not created."
}
if (-not (Test-Path -LiteralPath $updaterExe -PathType Leaf)) {
    throw "dist/release/ErrorLabsUpdater.exe was not created."
}

Write-Host "Production build created: $($projectRoot)\dist\release"
