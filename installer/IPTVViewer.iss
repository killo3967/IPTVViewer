; ============================================================
;  IPTVViewer - Instalador Inno Setup
;
;  Compilar desde la raiz del repo con:
;    ISCC.exe /DMyAppVersion=1.2.3 installer\IPTVViewer.iss
;
;  El workflow de GitHub Actions lo invoca automaticamente al
;  hacer push de un tag "v*" (ver .github/workflows/release.yml).
;
;  Nota: instalacion por usuario en %LocalAppData%\Programs para
;  que la app pueda escribir config.ini y logs/ junto al ejecutable
;  sin permisos de administrador (ver main.py).
; ============================================================

; Version inyectada desde la linea de comandos (/DMyAppVersion=...)
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "IPTVViewer"
#define MyAppPublisher "killo3967"
#define MyAppExeName "IPTVViewer.exe"

[Setup]
AppId={{8E1B9D3C-5A6F-4B2D-9C1E-3F4A5B6C7D8E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=IPTVViewer-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\IPTVViewer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
