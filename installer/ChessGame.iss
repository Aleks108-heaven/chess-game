; Inno Setup script for the Windows installer. Built by tools/build_release.py, which passes:
;   /DAppVersion=1.2.3  /DSourceDir=<dist\ChessGame>  /DOutputDir=<dist>  /DIconFile=<assets\icon.ico>
; Compile by hand with:  ISCC.exe /DAppVersion=... /DSourceDir=... /DOutputDir=... /DIconFile=... ChessGame.iss

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

; Per-user install by default (no administrator prompt); the wizard offers "for all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
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
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
