; An explicitly labelled test installer for the native-menu bundle.
; It never uses the older overlay-only dist/MyCareerTraining build.
#ifndef BuildId
  #error BuildId must be the exact candidate source commit
#endif
#ifndef BundleDir
  #error BundleDir must be the absolute short temporary bundle copy
#endif
#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif
#define AppName "My Career Training"

[Setup]
AppId={{17F0F7CD-13B7-4DBA-82C7-20AFA00D376C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} Windows test ({#BuildId})
AppPublisher=My Career Training contributors
AppPublisherURL=https://github.com/sloppamadewithlove/my-career-training
AppSupportURL=https://github.com/sloppamadewithlove/my-career-training/issues
DefaultDirName={localappdata}\Programs\My Career Training
DefaultGroupName={#AppName}
DisableProgramGroupPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\build\native-candidate\installers
OutputBaseFilename=MyCareerTraining-Windows-Test-{#BuildId}-Setup
SetupIconFile=..\src\my_career_training\ui\icon.ico
UninstallDisplayIcon={app}\MyCareerTraining.exe
LicenseFile=..\LICENSE
InfoBeforeFile=native-setup-info.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=MyCareerTraining.exe,MyCareerTrainingWorker.exe
RestartApplications=no
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a My Career Training desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
; BundleDir is a short absolute copy of the smoke-verified bundle. ISCC 6.7.3
; keeps a script-relative packaging\.. prefix and then rejects the resulting
; 260-character license path even though the file exists.
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove only the obsolete public helper when upgrading a previous app bundle.
Type: files; Name: "{app}\MyCareerTrainingWorker.exe"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\MyCareerTraining.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\MyCareerTraining.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MyCareerTraining.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent

; Saves live outside {app}. There is deliberately no AppData delete rule.
