#define MyAppName "Astro Dwarf Session"
#define MyAppVersion "1.7.5"
#define MyAppPublisher "ASD"
#define MyAppURL "https://github.com/styelz/astro_dwarf_session"
#define MyAppExeName "astro_dwarf_session_UI.exe"

[Setup]
AppId=587A2D8A-D16B-4A9F-B556-C377F0B957AD
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userappdata}\AstroDwarfSession
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
; Use relative path for GitHub Actions - license file will be in build output
LicenseFile=build\setupUI\frozen_application_license.txt
PrivilegesRequired=lowest
SolidCompression=yes
WizardStyle=modern
OutputDir=installer
OutputBaseFilename=AstroDwarfScheduler-Setup-win
; Use Install folder icon for consistency
SetupIconFile=Install\astro_dwarf_session_UI.ico
CloseApplications=yes
RestartApplications=no
AllowCancelDuringInstall=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "build\setupUI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Ensure the icon file is available in the app root directory for the application to use
Source: "Install\astro_dwarf_session_UI.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\astro_dwarf_session_UI.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
