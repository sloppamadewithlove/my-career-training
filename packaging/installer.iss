#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#define AppName "My Career Training"

[Setup]
AppId={{17F0F7CD-13B7-4DBA-82C7-20AFA00D376C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=My Career Training contributors
AppPublisherURL=https://github.com/sloppamadewithlove/my-career-training
AppSupportURL=https://github.com/sloppamadewithlove/my-career-training/issues
DefaultDirName={localappdata}\Programs\My Career Training
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=MyCareerTraining-{#AppVersion}-windows-x64-setup
SetupIconFile=..\src\my_career_training\ui\icon.ico
UninstallDisplayIcon={app}\MyCareerTraining.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut for offline My Career"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\MyCareerTraining\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\MyCareerTraining.exe"; Parameters: "--in-game"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\MyCareerTraining.exe"; Parameters: "--in-game"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\{#AppName} - Setup and diagnostics"; Filename: "{app}\MyCareerTraining.exe"; Parameters: "--manage"; WorkingDir: "{app}"

[Run]
Filename: "{app}\MyCareerTraining.exe"; Parameters: "--in-game"; Description: "Open offline {#AppName}"; Flags: nowait postinstall skipifsilent

; AppData careers are deliberately absent from Files, Dirs and UninstallDelete.
; Inno removes installed program files; it preserves the player's separate saves.
