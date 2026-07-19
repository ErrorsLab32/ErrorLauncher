; First-install package for ErrorLabs Playtest.
; Build values are supplied by scripts/package_launcher_release.ps1.

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef MyBuildDir
  #define MyBuildDir "..\\dist\\release"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\\release\\0.1.0"
#endif

#define MyAppName "ErrorLabs Playtest"
#define MyAppPublisher "ErrorLabs"
#define MyAppExeName "ErrorLabsPlaytest.exe"
; This identifier must remain stable across all launcher versions.
#define MyAppId "{{2AA0E755-5EF9-4D89-86D3-794698C4C3FA}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ErrorLabs Playtest
DefaultGroupName=ErrorLabs Playtest
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename=ErrorLabsPlaytestSetup-{#MyAppVersion}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
CloseApplicationsFilter=ErrorLabsPlaytest.exe
RestartApplications=no
UninstallDisplayName=Удалить ErrorLabs Playtest
Compression=lzma2
SolidCompression=yes

[Files]
Source: "{#MyBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Icons]
Name: "{group}\ErrorLabs Playtest"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\ErrorLabs Playtest"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить ErrorLabs Playtest"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
