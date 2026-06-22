[Setup]
AppName=Disk Space Analyzer
AppVersion=1.0
DefaultDirName={autopf}\Disk Space Analyzer
DefaultGroupName=Disk Space Analyzer
UninstallDisplayIcon={app}\disk_analyzer.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:\Inno Setup Output
OutputBaseFilename=DiskAnalyzer_Setup
PrivilegesRequired=admin

[Files]
; Fetch file from dist folder
Source: "C:\Users\steph\PycharmProjects\StorageAnalyzer\dist\disk_analyzer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Disk Space Analyzer"; Filename: "{app}\disk_analyzer.exe"

[Registry]
; --- RIGHT CLICK FOLDERS ---
; Høyreklikk direkte PÅ en mappe
Root: HKCR; Subkey: "Directory\shell\DiskAnalyzer"; ValueType: string; ValueData: "Analyze Disk Space"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\DiskAnalyzer\command"; ValueType: string; ValueData: """{app}\disk_analyzer.exe"" ""%1"""; Flags: uninsdeletekey

; Right click the empty space INSIDE a folder
Root: HKCR; Subkey: "Directory\Background\shell\DiskAnalyzer"; ValueType: string; ValueData: "Analyze Disk Space"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\DiskAnalyzer\command"; ValueType: string; ValueData: """{app}\disk_analyzer.exe"" ""%V"""; Flags: uninsdeletekey

; --- NEW: Right click disks/stations ---
; Right click directly on a disk/station (ex. C:, D:) under "This Computer"
Root: HKCR; Subkey: "Drive\shell\DiskAnalyzer"; ValueType: string; ValueData: "Analyze Disk Space"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Drive\shell\DiskAnalyzer\command"; ValueType: string; ValueData: """{app}\disk_analyzer.exe"" ""%1"""; Flags: uninsdeletekey