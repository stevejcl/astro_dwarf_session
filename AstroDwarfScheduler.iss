[Setup]
AppName=Astro Dwarf Scheduler
AppVersion=1.7.0
AppPublisher=Astro Dwarf Team
AppPublisherURL=https://github.com/styelz/astro_dwarf_session
AppSupportURL=https://github.com/styelz/astro_dwarf_session/issues
AppUpdatesURL=https://github.com/styelz/astro_dwarf_session/releases
DefaultDirName={userappdata}\AstroDwarfScheduler
DefaultGroupName=Astro Dwarf Scheduler
AllowNoIcons=yes
LicenseFile=
InfoBeforeFile=
InfoAfterFile=
OutputDir=installer
OutputBaseFilename=AstroDwarfScheduler-Setup
SetupIconFile=Install\astro_dwarf_session_UI.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
; Main GUI Application (exclude extern to avoid conflicts)
Source: "build\exe.win-amd64-3.12\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "extern"
; BLE Connect Utility (from extern folder if it exists)
Source: "build\exe.win-amd64-3.12\extern\*"; DestDir: "{app}\extern"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists(ExpandConstant('{src}\build\exe.win-amd64-3.12\extern'))
; Session directories (if they exist)
Source: "Astro_Sessions\*"; DestDir: "{app}\Astro_Sessions"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists(ExpandConstant('{src}\Astro_Sessions'))
; Documentation (if they exist)
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\README.md'))
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\CHANGELOG.md'))

[Icons]
Name: "{group}\Astro Dwarf Scheduler (GUI)"; Filename: "{app}\astro_dwarf_session_UI.exe"; WorkingDir: "{app}"; IconFilename: "{app}\astro_dwarf_session_UI.ico"
Name: "{group}\Astro Dwarf Scheduler (Console)"; Filename: "{app}\astro_dwarf_scheduler.exe"; WorkingDir: "{app}"
Name: "{group}\Dwarfium BLE Connect"; Filename: "{app}\extern\connect_bluetooth.exe"; WorkingDir: "{app}\extern"
Name: "{group}\{cm:UninstallProgram,Astro Dwarf Scheduler}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Astro Dwarf Scheduler"; Filename: "{app}\astro_dwarf_session_UI.exe"; WorkingDir: "{app}"; IconFilename: "{app}\astro_dwarf_session_UI.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Astro Dwarf Scheduler"; Filename: "{app}\astro_dwarf_session_UI.exe"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\astro_dwarf_session_UI.exe"; Description: "{cm:LaunchProgram,Astro Dwarf Scheduler}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Astro_Sessions"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\*.log"

[Code]
// File and directory existence check functions
function FileExists(FileName: string): Boolean;
begin
  Result := FileExists(FileName);
end;

function DirExists(DirName: string): Boolean;
begin
  Result := DirExists(DirName);
end;

function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}_is1');
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

function UnInstallOldVersion(): Integer;
var
  sUnInstallString: String;
  iResultCode: Integer;
begin
  Result := 0;
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then begin
    sUnInstallString := RemoveQuotes(sUnInstallString);
    if Exec(sUnInstallString, '/SILENT /NORESTART /SUPPRESSMSGBOXES','', SW_HIDE, ewWaitUntilTerminated, iResultCode) then
      Result := 3
    else
      Result := 2;
  end else
    Result := 1;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep=ssInstall) then
  begin
    if (IsUpgrade()) then
    begin
      UnInstallOldVersion();
    end;
  end;
end;
