; Installeur Windows de Spool Manager.
; Compilation : ISCC.exe installer\spoolmanager.iss
; (après python -m PyInstaller --noconfirm SpoolManager.spec)

#define MyAppName "Spool Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Spool Manager"
#define MyAppExeName "SpoolManager.exe"
#define MyAppURL "https://github.com/serge/spool-manager"

#ifndef OutputDirOverride
  #define OutputDirOverride "output"
#endif

[Setup]
AppId={{8E2C1F4A-9B7D-4E11-A3C6-5F8D2A1B0E77}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\SpoolManager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDirOverride}
OutputBaseFilename=SpoolManager-{#MyAppVersion}-Setup
Compression=zip
SolidCompression=no
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\docs\spoolmanager.ico
WizardSizePercent=120
CloseApplications=yes
RestartApplications=no
MinVersion=10.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"
Name: "autostart"; Description: "Démarrer avec Windows (zone de notification)"; GroupDescription: "Démarrage :"; Flags: unchecked

[Files]
Source: "..\dist\SpoolManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SpoolManager"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer Spool Manager"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
