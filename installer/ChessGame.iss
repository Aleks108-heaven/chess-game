; Inno Setup script for the Windows installer. Built by tools/build_release.py, which passes:
;   /DAppVersion=1.2.3  /DSourceDir=<dist\ChessGame>  /DOutputDir=<dist>  /DIconFile=<assets\icon.ico>
; Compile by hand with:  ISCC.exe /DAppVersion=... /DSourceDir=... /DOutputDir=... /DIconFile=... ChessGame.iss
;
; The game installs into Program Files for all users, which needs administrator approval (a UAC
; prompt). That keeps the program files out of reach of anything running as a standard user and
; is where managed-device policies (AppLocker and similar) expect an application to live. It does
; NOT remove the "unknown publisher" SmartScreen warning: only code signing does that.
; Without administrator rights, run the setup with /CURRENTUSER (a per-user install under
; %LOCALAPPDATA%\Programs) or use the portable zip.

#ifndef AppVersion
  #error Pass /DAppVersion=x.y.z (tools/build_release.py does this).
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=<folder holding the PyInstaller output>.
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

#define AppName "Chess Game"
#define AppExe "ChessGame.exe"
#define AppUrl "https://github.com/Aleks108-heaven/chess-game"
; The same GUID as AppId below, written without the doubled brace, for the registry lookup.
#define AppGuid "{77095F83-B76B-45F3-AB55-E06CF7B9F6A0}"

[Setup]
; Never change AppId: it is how upgrades and the uninstaller recognise this program.
AppId={{77095F83-B76B-45F3-AB55-E06CF7B9F6A0}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Aleks108-heaven
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup

; Install for all users into Program Files (64-bit). "commandline" keeps /CURRENTUSER available
; for the build script's unattended test install and for people without administrator rights.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir={#OutputDir}
OutputBaseFilename=ChessGame-v{#AppVersion}-windows-x64-setup
#ifdef IconFile
SetupIconFile={#IconFile}
#endif
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Lets an upgrade replace a running copy of the game after asking the user to close it.
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; README.txt is written for the portable zip ("no installation"), so it is not installed.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "README.txt"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; runasoriginaluser: the installer is elevated, but the game must not be.
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
// Releases up to 1.1.0 installed per user (into %LOCALAPPDATA%\Programs) and Windows tracks that
// separately from an all-users install, so installing 1.2.0 over it would leave two copies and
// two Start Menu entries. Once the user has chosen to install, remove the old per-user copy.

function OldPerUserUninstaller(): String;
var
  Command: String;
begin
  Result := '';
  if RegQueryStringValue(HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppGuid}_is1',
      'UninstallString', Command) then
  begin
    Result := RemoveQuotes(Trim(Command));
    if not FileExists(Result) then
      Result := '';
  end;
end;

procedure RemoveOldPerUserCopy();
var
  Uninstaller: String;
  ResultCode, Waited: Integer;
begin
  Uninstaller := OldPerUserUninstaller();
  if Uninstaller = '' then
    Exit;
  Log('Removing the earlier per-user installation: ' + Uninstaller);
  if not Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE,
              ewWaitUntilTerminated, ResultCode) then
  begin
    Log('Could not start the old uninstaller (' + SysErrorMessage(ResultCode) + '); leaving it.');
    Exit;
  end;
  // An Inno uninstaller finishes from a temporary copy of itself: wait until it is gone.
  Waited := 0;
  while FileExists(Uninstaller) and (Waited < 30000) do
  begin
    Sleep(250);
    Waited := Waited + 250;
  end;
  Log('Earlier per-user installation removed: ' + IntToStr(Ord(not FileExists(Uninstaller))));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) and IsAdminInstallMode then
    RemoveOldPerUserCopy();
end;
