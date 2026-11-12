; Wrench installer (Inno Setup 6). Build: scripts/build-installer.ps1
; or: iscc /DAppVersion=<version> installer\wrench.iss

#ifndef AppVersion
  #error AppVersion is not defined. Run: iscc /DAppVersion=<version> installer\wrench.iss
#endif

#define AppMutexName "Local\WrenchSingleInstance"

[Setup]
AppId={{DF1A711B-045E-48E1-A43E-DCBD79719B83}
AppName=Wrench
AppVersion={#AppVersion}
AppPublisher=Ergorock
AppPublisherURL=https://github.com/Ergorock/wrench
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Wrench
DisableDirPage=yes
DisableProgramGroupPage=yes
DefaultGroupName=Wrench
OutputDir=Output
OutputBaseFilename=Wrench-Setup-{#AppVersion}
SetupIconFile=..\backend\assets\wrench.ico
UninstallDisplayIcon={app}\Wrench.exe
Compression=lzma2
SolidCompression=yes
AppMutex={#AppMutexName}
ShowLanguageDialog=no
#ifexist "..\LICENSE"
LicenseFile=..\LICENSE
#endif

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Wrench\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Wrench"; Filename: "{app}\Wrench.exe"
Name: "{autodesktop}\Wrench"; Filename: "{app}\Wrench.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Wrench.exe"; Description: "{cm:LaunchProgram,Wrench}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Wrench.exe"; Flags: nowait; Check: ShouldRelaunch

[CustomMessages]
french.DeleteUserData=Supprimer aussi vos paramètres et données (%1) ?
english.DeleteUserData=Also delete your settings and data (%1)?

[Code]
const
  MutexWaitMaxMs = 30000;
  MutexWaitStepMs = 250;

// Silent update: the updater starts the setup then quits Wrench, so the
// AppMutex check (which aborts silently, without retry) can run too early.
// Wait for Wrench to exit first; the built-in AppMutex check still has the
// final say.
function InitializeSetup: Boolean;
var
  Waited: Integer;
begin
  Result := True;
  if not WizardSilent then
    Exit;
  if not CheckForMutexes('{#AppMutexName}') then
    Exit;
  Log('Wrench is running; waiting for it to exit (silent install).');
  Waited := 0;
  while CheckForMutexes('{#AppMutexName}') and (Waited < MutexWaitMaxMs) do
  begin
    Sleep(MutexWaitStepMs);
    Waited := Waited + MutexWaitStepMs;
  end;
  if CheckForMutexes('{#AppMutexName}') then
    Log('Wrench still running after wait; AppMutex check will decide.')
  else
    Log(Format('Wrench exited after %d ms.', [Waited]));
end;

function ShouldRelaunch: Boolean;
var
  I: Integer;
begin
  Result := False;
  if not WizardSilent then
    Exit;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/RELAUNCH') = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Wrench');
    if not UninstallSilent then
    begin
      DataDir := ExpandConstant('{userappdata}\Wrench');
      if MsgBox(FmtMessage(CustomMessage('DeleteUserData'), [DataDir]),
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
