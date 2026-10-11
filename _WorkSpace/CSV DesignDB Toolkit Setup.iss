[Setup]
; 프로그램 기본 정보
AppName=CSV DesignDB Toolkit
AppVersion=1.2.3
AppPublisher=YCJ
AppPublisherURL=https://github.com/C01000011J01001010/CSV-DesignDB-Toolkit

; 제어판에 표시될 기본 설치 경로 (C:\Program Files\CSV DesignDB Toolkit)
DefaultDirName={autopf}\CSV DesignDB Toolkit
DisableProgramGroupPage=yes

; 출력될 설치 파일 이름
OutputBaseFilename=CSV_DesignDB_Toolkit_Setup_v1.2.3
Compression=lzma
SolidCompression=yes

; 관리자 권한 요구
PrivilegesRequired=admin

; 아이콘 설정 (경로에 맞게 수정 필요)
SetupIconFile=compiler:SetupClassicIcon.ico
UninstallDisplayIcon={app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe

[Files]
Source: "C:\GitHub Release\CSV-DesignDB-Toolkit\_WorkSpace\dist\CSV_DesignDB_Toolkit_Setup_v1.2.3\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\GitHub Release\CSV-DesignDB-Toolkit\_WorkSpace\dist\CSV_DesignDB_Toolkit_Setup_v1.2.3\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 바탕화면 및 시작 메뉴 바로가기
Name: "{autoprograms}\CSV DesignDB Toolkit"; Filename: "{app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"
Name: "{autodesktop}\CSV DesignDB Toolkit"; Filename: "{app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"

[Registry]
; 1. 폴더를 우클릭했을 때 나타나는 메뉴
Root: HKCR; Subkey: "Directory\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: ""; ValueData: "Open CSV DesignDB Toolkit Here"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\CSVDesignDBToolkit\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"" ""%V"""; Flags: uninsdeletekey

; 2. 폴더 내부 빈 공간을 우클릭했을 때 나타나는 메뉴
Root: HKCR; Subkey: "Directory\Background\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: ""; ValueData: "Open CSV DesignDB Toolkit Here"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\CSVDesignDBToolkit\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CSV_DesignDB_Toolkit_Setup_v1.2.3.exe"" ""%V"""; Flags: uninsdeletekey