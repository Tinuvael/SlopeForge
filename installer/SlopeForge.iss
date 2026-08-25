#ifndef AppVersion
  #error AppVersion must be supplied by build_release.bat
#endif

#define AppName "SlopeForge"
#define AppPublisher "Емшанов Евгений"
#define AppURL "https://github.com/Tinuvael/SlopeForge"
#define AppExeName "SlopeForge.exe"
#define UpdaterExeName "SlopeForgeUpdater.exe"

[Setup]
AppId={{D24878F9-0D8A-4C90-A1ED-E9E42007114B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf64}\SlopeForge
DefaultGroupName=SlopeForge
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=SlopeForge-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\app\icons\slopeforge_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\SlopeForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SlopeForge"; Filename: "{app}\{#AppExeName}"
Name: "{group}\SlopeForge Updater"; Filename: "{app}\{#UpdaterExeName}"
Name: "{autodesktop}\SlopeForge"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch SlopeForge"; Flags: nowait postinstall skipifsilent
