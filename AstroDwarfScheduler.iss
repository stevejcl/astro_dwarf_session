[Setup]
AppName=Astro Dwarf Scheduler
AppVersion=1.7.0
AppId={{8A9B2C3D-4E5F-6789-ABCD-EF0123456789}
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
CloseApplications=yes
RestartApplications=no
AllowCancelDuringInstall=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
; Main GUI Application
Source: "build\exe.win-amd64-3.12\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Install folder contents (config files, icons, etc.)
Source: "Install\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Session directories (if they exist)
Source: "Astro_Sessions\*"; DestDir: "{app}\Astro_Sessions"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists(ExpandConstant('{src}\Astro_Sessions'))
; Documentation (if they exist)
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\README.md'))
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\CHANGELOG.md'))

[InstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\*.log"
Type: files; Name: "{app}\*.tmp"

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

// Terminate running application processes
function TerminateApp(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Try to terminate the main application gracefully
  if Exec('taskkill', '/F /IM astro_dwarf_session_UI.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Sleep(1000);
  // Try to terminate the BLE connect utility
  if Exec('taskkill', '/F /IM connect_bluetooth.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Sleep(1000);
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
    // Use more aggressive silent uninstall flags
    if Exec(sUnInstallString, '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES /FORCECLOSEAPPLICATIONS','', SW_HIDE, ewWaitUntilTerminated, iResultCode) then
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
    // Always terminate running applications before install
    TerminateApp();
    if (IsUpgrade()) then
    begin
      UnInstallOldVersion();
    end;
  end;
end;
