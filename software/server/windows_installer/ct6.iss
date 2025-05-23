; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define MyAppName "CT6"
#define MyAppVersion "11.7"
#define MyAppPublisher "Paul Austen"
#define MyAppURL "https://github.com/pjaos/ct6_meter_os"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{7D2FD671-B666-48D5-AF97-00B139D4A505}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Put install folder in root of C drive. E.G C:\CT6
; so it is writable as this is needed for mpy_cross
DefaultDirName={sd}\Python_Program_Files\{#MyAppName}
DisableDirPage=yes
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=C:\git_repos\ct6_meter_os\LICENSE.txt
; Remove the following line to run in administrative install mode (install for all users.)
PrivilegesRequired=lowest
OutputDir=..\installers
OutputBaseFilename=CT6_{#MyAppVersion}
SetupIconFile=../assets/icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Icons]
Name: "{group}\CT6 Configurator"; Filename: "{app}\ct6_configurator.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 App"; Filename: "{app}\ct6_app.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 DB Store"; Filename: "{app}\ct6_db_store.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 Dash"; Filename: "{app}\ct6_dash.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 Dash Manager"; Filename: "{app}\ct6_dash_mgr.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 Stats"; Filename: "{app}\ct6_stats.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 Shell"; Filename: "{app}\start_powershell.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\CT6 Uninstall"; Filename: "{uninstallexe}"

[Files]
Source: "../../../LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "../../../README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "../pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "../assets/*"; DestDir: "{app}/assets/"; Flags: ignoreversion
Source: "../ct6/*"; DestDir: "{app}/ct6/"; Flags: ignoreversion recursesubdirs
Source: "../lib/*"; DestDir: "{app}/lib/"; Flags: ignoreversion recursesubdirs
Source: "../picow/*"; DestDir: "{app}/picow/"; Flags: ignoreversion recursesubdirs
Source: "ct6_configurator.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_dash_mgr.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_dash.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_app.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_db_store.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_mfg_tool.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_tool.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ct6_stats.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "show_env_path.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "start_powershell.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "install.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall.bat"; DestDir: "{app}"; Flags: ignoreversion

;[Run]
;Filename: "{app}\install.bat"; Parameters: "install"; Check: CheckReturnCode

[UninstallRun]
Filename: "{app}\uninstall.bat"; RunOnceId: "pipxuninstall"
; Flags: runhidden;

[Code]
// Check for Python.org Python (checks 64-bit and 32-bit registry keys)
function IsPythonOrgInstalled(): Boolean;
var
  KeyNames: TArrayOfString;
  I: Integer;
  InstallPath: string;
begin
  Result := False;

  // Check current user install
  if RegGetSubkeyNames(HKEY_CURRENT_USER, 'Software\Python\PythonCore', KeyNames) then
  begin
    for I := 0 to GetArrayLength(KeyNames) - 1 do
    begin
      if RegQueryStringValue(HKEY_CURRENT_USER,
          'Software\Python\PythonCore\' + KeyNames[I] + '\InstallPath', '', InstallPath) then
      begin
        if FileExists(InstallPath + 'python.exe') then
        begin
          Result := True;
          Exit;
        end;
      end;
    end;
  end;
end;
function InitializeSetup(): Boolean;
begin
  if not IsPythonOrgInstalled() then begin
    MsgBox(
      'Python is not installed.' + #13#13 +
      'You May have Microsoft Python installed but this program needs the python.org version. Please install it from:' + #13#13 +
      'https://www.python.org/downloads/windows/' + #13#13 +
      'Selecting "Use admin privalages when installing py.exe" and "Add python.exe to PATH" checkboxes.' + #13#13 +
      'Setup will now exit.',
      mbError, MB_OK
    );
    Result := False;
  end else begin
    Result := True;
  end;
end;

var
  BatchFileResultCode: Integer;
  msg: String;
function ExecuteBatchFileAndCheck: Boolean;
begin
  // Execute the batch file
  if Exec(ExpandConstant('{app}\install.bat'), '', '', SW_SHOWNORMAL , ewWaitUntilTerminated, BatchFileResultCode) then
  begin
    Result := False;
    // Check the return code
    if BatchFileResultCode = 0 then
    begin
      Result := True;
    end
    else if BatchFileResultCode = 2 then
    begin
      msg := 'Now python is installed please try again.';
      Log(msg);
      MsgBox(msg, mbError, MB_OK);
    end
    else
    begin
      msg := 'Installation failed.'
      Log(msg);
      MsgBox(msg, mbError, MB_OK);
    end;
  end
  else
  begin
    msg := 'Failed to execute install.bat file.'
    Log(msg);
    MsgBox(msg, mbError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not ExecuteBatchFileAndCheck then
    begin
      // If the batch file execution fails, abort the setup
      WizardForm.Close;
    end;
  end;
end;
