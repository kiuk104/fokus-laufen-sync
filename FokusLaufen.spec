# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정 — Windows 에서: pyinstaller --noconfirm --clean FokusLaufen.spec
# 결과: dist/FokusLaufen/FokusLaufen.exe (폴더째 설치 파일에 묶음. 한 파일(onefile)보다 빨리 뜨고 백신 오탐이 적음)
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

VERSION = re.search(r'^VERSION = "([^"]+)"', Path("fokus_sync.py").read_text(encoding="utf-8"), re.M).group(1)
nums = tuple(int(x) for x in (VERSION.split(".") + ["0"] * 4)[:4])

datas = [("assets", "assets")]
binaries, hidden = [], ["fokus_ui"]
for pkg in ("curl_cffi", "garminconnect", "ua_generator", "segno"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h

version_info = None
if sys.platform == "win32":  # exe 속성(파일 설명·버전). 리눅스에서 시험 빌드할 땐 건너뜀
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                     VarFileInfo, VarStruct, VSVersionInfo)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[
            StringFileInfo([StringTable("041204B0", [
                StringStruct("CompanyName", "Fokus Laufen"),
                StringStruct("FileDescription", "Fokus Laufen PC 동기화"),
                StringStruct("FileVersion", VERSION),
                StringStruct("InternalName", "FokusLaufen"),
                StringStruct("OriginalFilename", "FokusLaufen.exe"),
                StringStruct("ProductName", "Fokus Laufen PC 동기화"),
                StringStruct("ProductVersion", VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0412, 1200])]),
        ],
    )

a = Analysis(
    ["fokus_app.py"],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["pytest", "PIL", "numpy"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FokusLaufen",
    console=False,          # 검은 창 없음
    icon="assets/icon.ico",
    version=version_info,
    upx=False,              # UPX 압축은 백신 오탐을 늘려서 끔
)
coll = COLLECT(exe, a.binaries, a.datas, name="FokusLaufen", upx=False)
