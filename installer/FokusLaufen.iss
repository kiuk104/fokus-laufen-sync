; Fokus Laufen PC 동기화 — Windows 설치 파일 (Inno Setup 6)
; GitHub Actions 가 만듦: pyinstaller FokusLaufen.spec → iscc installer\FokusLaufen.iss → dist\FokusLaufen-Setup.exe
; 관리자 권한 없이 내 계정에만 설치 ({localappdata}\Programs\FokusLaufen). 설정·기록은 {localappdata}\FokusLaufen

#define AppVersion GetEnv("FL_VERSION")
#if AppVersion == ""
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8C1E3F52-6A2B-4C7D-9E10-FA11A9ED2026}
AppName=Fokus Laufen PC 동기화
AppVersion={#AppVersion}
AppVerName=Fokus Laufen PC 동기화 {#AppVersion}
AppPublisher=Fokus Laufen
AppPublisherURL=https://fokus-laufen.web.app
AppSupportURL=https://github.com/kiuk104/fokus-laufen-sync
DefaultDirName={localappdata}\Programs\FokusLaufen
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=FokusLaufen-Setup
SetupIconFile=..\assets\icon.ico
WizardSmallImageFile=..\assets\wizard-small.bmp
WizardStyle=modern
UninstallDisplayIcon={app}\FokusLaufen.exe
UninstallDisplayName=Fokus Laufen PC 동기화
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Fokus Laufen PC 동기화 설치
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

[Languages]
#if FileExists(AddBackslash(CompilerPath) + "Languages\Korean.isl")
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; Flags: unchecked

[Files]
Source: "..\dist\FokusLaufen\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 업데이트 때 예전 버전의 묶음 파일이 섞이지 않게
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
; AppUserModelID 가 있어야 Windows 알림에 "Fokus Laufen" 이름과 아이콘이 붙음 (fokus_app.AUMID 와 같아야 함)
Name: "{autoprograms}\Fokus Laufen"; Filename: "{app}\FokusLaufen.exe"; AppUserModelID: "FokusLaufen.PCSync"; Comment: "가민 기록을 Fokus Laufen 앱으로 보내기"
Name: "{autodesktop}\Fokus Laufen"; Filename: "{app}\FokusLaufen.exe"; AppUserModelID: "FokusLaufen.PCSync"; Tasks: desktopicon

[Run]
Filename: "{app}\FokusLaufen.exe"; Description: "Fokus Laufen 열기 (설정 시작)"; Flags: nowait postinstall skipifsilent
; 프로그램 창의 '지금 업데이트'로 조용히 설치했을 때(/relaunch=1) 창을 다시 엶. 자동 실행(--auto)의 업데이트는 다시 열지 않음
Filename: "{app}\FokusLaufen.exe"; Flags: nowait; Check: RelaunchRequested

[UninstallRun]
; 자동 실행(작업 스케줄러) 지우기
Filename: "{app}\FokusLaufen.exe"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "unregister"

[Code]
function RelaunchRequested: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:relaunch|0}') = '1');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dir := ExpandConstant('{localappdata}\FokusLaufen');
    if DirExists(Dir) and (not UninstallSilent) then
      if MsgBox('이 PC에 남은 가민 로그인 정보와 받은 기록도 지울까요?' + #13#10 + #13#10 +
                '앱에 이미 올린 기록은 그대로 남아요.' + #13#10 + Dir,
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Dir, True, True, True);
  end;
end;
