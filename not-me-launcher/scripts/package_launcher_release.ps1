param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"

function Find-InnoSetupCompiler {
    $candidates = @(@(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) })

    if ($candidates.Count -gt 0) {
        return (Resolve-Path -LiteralPath $candidates[0]).Path
    }

    $fromPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "Inno Setup не установлен. Установите Inno Setup 6 (включая ISCC.exe) и повторите сборку."
}

function Assert-ReleasePayload {
    param([string]$BuildDirectory)

    $forbidden = Get-ChildItem -LiteralPath $BuildDirectory -Force -Recurse | Where-Object {
        $_.Name -ieq ".env" -or
        $_.Name -ieq "installation.json" -or
        $_.Name -like "*.part" -or
        $_.FullName -match "[\\/](\.git|\.github|\.venv|__pycache__|tests|downloads|logs)[\\/]"
    }
    if ($forbidden) {
        $names = ($forbidden | Select-Object -ExpandProperty FullName) -join ", "
        throw "Release payload contains forbidden files: $names"
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$iscc = Find-InnoSetupCompiler
if (-not $PythonExecutable) {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $PythonExecutable = if (Test-Path -LiteralPath $venvPython) {
        $venvPython
    } else {
        "python"
    }
}

$rawVersion = $Version.Trim()
if ($rawVersion.StartsWith("v", [StringComparison]::OrdinalIgnoreCase)) {
    $rawVersion = $rawVersion.Substring(1)
}
$normalizedVersion = (& $PythonExecutable -c "from packaging.version import Version; import sys; print(Version(sys.argv[1]))" $rawVersion).Trim()
if ($LASTEXITCODE -ne 0 -or -not $normalizedVersion) {
    throw "Invalid launcher version: $Version"
}

$versionFile = Join-Path $projectRoot "launcher\version.py"
$configFile = Join-Path $projectRoot "launcher\config.py"
$originalVersionFile = [IO.File]::ReadAllText($versionFile)
$originalConfigFile = [IO.File]::ReadAllText($configFile)
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$gameReleasesToken = $env:GAME_RELEASES_TOKEN
if ([string]::IsNullOrWhiteSpace($gameReleasesToken)) {
    throw "GAME_RELEASES_TOKEN must be set for a production release build."
}
$encodedGameReleasesToken = [Convert]::ToBase64String($utf8NoBom.GetBytes($gameReleasesToken))
try {
    [IO.File]::WriteAllText($versionFile, "LAUNCHER_VERSION = `"$normalizedVersion`"`n", $utf8NoBom)
    $buildConfig = $originalConfigFile.Replace(
        'BUILT_GAME_RELEASES_TOKEN_B64 = ""',
        "BUILT_GAME_RELEASES_TOKEN_B64 = `"$encodedGameReleasesToken`""
    )
    if ($buildConfig -eq $originalConfigFile) {
        throw "Could not inject the production game release credential."
    }
    [IO.File]::WriteAllText($configFile, $buildConfig, $utf8NoBom)
    & (Join-Path $PSScriptRoot "build_launcher.ps1") -PythonExecutable $PythonExecutable
} finally {
    [IO.File]::WriteAllText($versionFile, $originalVersionFile, $utf8NoBom)
    [IO.File]::WriteAllText($configFile, $originalConfigFile, $utf8NoBom)
}

$buildDirectory = Join-Path $projectRoot "dist\release"
foreach ($requiredFile in @("ErrorLabsPlaytest.exe", "ErrorLabsUpdater.exe")) {
    if (-not (Test-Path -LiteralPath (Join-Path $buildDirectory $requiredFile) -PathType Leaf)) {
        throw "Production build is missing $requiredFile."
    }
}
Assert-ReleasePayload -BuildDirectory $buildDirectory

$releaseRoot = Join-Path $projectRoot "release"
$releaseDirectory = Join-Path $releaseRoot $normalizedVersion
if (Test-Path -LiteralPath $releaseDirectory) {
    $resolvedOutputRoot = (Resolve-Path -LiteralPath $releaseRoot).Path
    $resolvedRelease = (Resolve-Path -LiteralPath $releaseDirectory).Path
    if (-not $resolvedRelease.StartsWith($resolvedOutputRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Invalid release directory."
    }
    Remove-Item -LiteralPath $resolvedRelease -Recurse -Force
}
New-Item -ItemType Directory -Path $releaseDirectory | Out-Null

$zipName = "ErrorLabsPlaytest-$normalizedVersion-win-x64.zip"
$zipPath = Join-Path $releaseDirectory $zipName
Compress-Archive -Path (Join-Path $buildDirectory "*") -DestinationPath $zipPath -CompressionLevel Optimal

$sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$manifestPath = Join-Path $releaseDirectory "launcher-manifest.json"
$manifest = [ordered]@{
    version = $normalizedVersion
    platform = "windows-x64"
    asset = $zipName
    entrypoint = "ErrorLabsPlaytest.exe"
    sha256 = $sha256
}
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json) + "`n", $utf8NoBom)

$verifiedManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($verifiedManifest.version -ne $normalizedVersion) {
    throw "Manifest version does not match the build version."
}
if ($verifiedManifest.asset -ne $zipName -or -not (Test-Path -LiteralPath $zipPath)) {
    throw "The ZIP selected by the manifest does not exist."
}
$repeatHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($verifiedManifest.sha256 -ne $repeatHash) {
    throw "Manifest SHA-256 does not match the ZIP."
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entryNames = @($archive.Entries | ForEach-Object FullName)
    foreach ($requiredFile in @("ErrorLabsPlaytest.exe", "ErrorLabsUpdater.exe")) {
        if ($entryNames -notcontains $requiredFile) {
            throw "$requiredFile is missing from the ZIP root."
        }
    }
    if ($entryNames | Where-Object { $_ -match "(^|/)(\.env|installation\.json|.*\.part)$" }) {
        throw "The ZIP contains a forbidden runtime or secret file."
    }
} finally {
    $archive.Dispose()
}

$installerScript = Join-Path $projectRoot "installer\ErrorLabsPlaytest.iss"
& $iscc "/DMyAppVersion=$normalizedVersion" "/DMyBuildDir=$buildDirectory" "/DMyOutputDir=$releaseDirectory" $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup could not build the installer."
}

$setupName = "ErrorLabsPlaytestSetup-$normalizedVersion.exe"
$setupPath = Join-Path $releaseDirectory $setupName
if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
    throw "Installer output is missing: $setupName"
}

Write-Host "Release assets are ready:"
Write-Host $setupPath
Write-Host $zipPath
Write-Host $manifestPath
Write-Host "SHA-256: $sha256"
