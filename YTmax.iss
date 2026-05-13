; ──────────────────────────────────────────────────────────────────────────────
; YTmax Inno Setup Installer Script
; Build:  Open this file in Inno Setup IDE and click Compile (Ctrl+F9)
; ──────────────────────────────────────────────────────────────────────────────

#define AppName       "YTmax"
#define AppVersion    "1.0.0"
#define AppPublisher  "shenfurkan"
#define AppURL        "https://github.com/shenfurkan/YTmax"
#define AppExeName    "YTmax.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=installer_output
OutputBaseFilename=YTmax-Setup-{#AppVersion}
SetupIconFile=ytmax.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ── License / Info ─────────────────────────────────────────────────────────────
; Uncomment if you have a license file:
; LicenseFile=LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish";  MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main executable (built by PyInstaller — must run build.py first)
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; ── Prerequisites check note ──────────────────────────────────────────────────
; FFmpeg and Node.js must be installed separately on the target system.
; They are NOT bundled. The app checks for them at startup (status bar indicators).

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
