; Wrench installer (NSIS 3). Build: scripts/build-installer.ps1
; or: makensis /DAPP_VERSION=<version> /DAPP_VERSION_NUMERIC=<X.Y.Z.0> installer\wrench.nsi

!ifndef APP_VERSION
  !error "APP_VERSION is not defined. Run: makensis /DAPP_VERSION=<version> installer\wrench.nsi"
!endif
; VIProductVersion needs X.Y.Z.0 (no -beta... suffix): the build script passes it.
!ifndef APP_VERSION_NUMERIC
  !define APP_VERSION_NUMERIC "${APP_VERSION}.0"
!endif

!define APP_ID "{DF1A711B-045E-48E1-A43E-DCBD79719B83}"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
!define MUTEX_NAME "Local\WrenchSingleInstance"

Unicode true
Name "Wrench"
; makensis does not create the output folder.
!system 'if not exist "Output" mkdir "Output"'
OutFile "Output\Wrench-Setup-${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\Wrench"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define MUI_ICON "..\backend\assets\wrench.ico"
!define MUI_UNICON "..\backend\assets\wrench.ico"

; Installer pages
!insertmacro MUI_PAGE_WELCOME
!if /FileExists "..\LICENSE"
  !insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!endif
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\Wrench.exe"
; The "show readme" checkbox is reused for the desktop shortcut.
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "$(DesktopShortcut)"
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateDesktopShortcut
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; No language dialog: NSIS picks the Windows language when available, else the
; first language below, hence English first.
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"

!include "lang_en.nsh"
!include "lang_fr.nsh"

VIProductVersion "${APP_VERSION_NUMERIC}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductName" "Wrench"
VIAddVersionKey /LANG=${LANG_ENGLISH} "CompanyName" "Ergorock"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileDescription" "Wrench Setup"

; Waits until Wrench is closed (single-instance mutex released).
; Silent: polls every 250 ms for at most 30 s, then exits with code 2.
; Interactive: Retry / Cancel message box.
!macro WAIT_FOR_WRENCH PREFIX
Function ${PREFIX}WaitForWrench
  StrCpy $1 0
  ${Do}
    ; 0x00100000 = SYNCHRONIZE
    System::Call 'kernel32::OpenMutexW(i 0x00100000, i 0, w "${MUTEX_NAME}") p.r0'
    ${If} $0 = 0
      Return
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
    ${If} ${Silent}
      ${If} $1 >= 120
        SetErrorLevel 2
        Quit
      ${EndIf}
      Sleep 250
      IntOp $1 $1 + 1
    ${Else}
      ${If} ${Cmd} `MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "$(WrenchRunning)" IDCANCEL`
        Quit
      ${EndIf}
    ${EndIf}
  ${Loop}
FunctionEnd
!macroend
!insertmacro WAIT_FOR_WRENCH ""
!insertmacro WAIT_FOR_WRENCH "un."

Function .onInit
  SetShellVarContext current
  Call WaitForWrench
FunctionEnd

Function un.onInit
  SetShellVarContext current
  Call un.WaitForWrench
FunctionEnd

Function CreateDesktopShortcut
  CreateShortCut "$DESKTOP\Wrench.lnk" "$INSTDIR\Wrench.exe"
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  ; Removes files of a previous version that are no longer shipped.
  RMDir /r "$INSTDIR\_internal"
  File /r "..\dist\Wrench\*"

  WriteUninstaller "$INSTDIR\uninstall.exe"

  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Wrench"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Ergorock"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\Wrench.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "URLInfoAbout" "https://github.com/Ergorock/wrench"
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" $0

  CreateShortCut "$SMPROGRAMS\Wrench.lnk" "$INSTDIR\Wrench.exe"

  ; /RELAUNCH (silent update only): start Wrench again.
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/RELAUNCH" $R1
  ${IfNot} ${Errors}
  ${AndIf} ${Silent}
    Exec '"$INSTDIR\Wrench.exe"'
  ${EndIf}
SectionEnd

Section "Uninstall"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Wrench"

  ${IfNot} ${Silent}
    ${If} ${Cmd} `MessageBox MB_YESNO|MB_DEFBUTTON2|MB_ICONQUESTION "$(DeleteUserData)" IDYES`
      RMDir /r "$APPDATA\Wrench"
    ${EndIf}
  ${EndIf}

  Delete "$SMPROGRAMS\Wrench.lnk"
  Delete "$DESKTOP\Wrench.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd
