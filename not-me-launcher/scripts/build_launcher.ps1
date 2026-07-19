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
if (-not (Test-Path -LiteralPath $launcherExe -PathType Leaf)) {
    throw "dist/release/ErrorLabsPlaytest.exe was not created."
}
if (-not (Test-Path -LiteralPath $updaterExe -PathType Leaf)) {
    throw "dist/release/ErrorLabsUpdater.exe was not created."
}

Write-Host "Production build created: $($projectRoot)\dist\release"
