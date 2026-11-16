# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置：生成 onedir 程序 dist/VideoStudyGuardian/VideoStudyGuardian.exe
# 用法（在仓库根目录）：pyinstaller --noconfirm windows/VideoStudyGuardian.spec
import os
from PyInstaller.utils.hooks import collect_submodules

HERE = os.path.abspath(SPECPATH)
ROOT = os.path.dirname(HERE)

hidden = ["questions", "vsg_core", "vsg_winsys", "vsg_media", "vsg_gui"]
try:  # 可选：Windows 媒体会话检测
    import winsdk  # noqa: F401
    for pkg in ("winsdk.windows.media.control", "winsdk.windows.media", "winsdk.windows.foundation"):
        hidden += collect_submodules(pkg)
except Exception:
    pass

a = Analysis(
    [os.path.join(HERE, "vsg_windows.py")],
    pathex=[HERE, ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "bank"), "bank"), (os.path.join(ROOT, "questions.py"), ".")],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["gi", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VideoStudyGuardian",
    console=False,
    debug=False,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VideoStudyGuardian")
