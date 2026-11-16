#!/usr/bin/env python3
"""在 Windows 上打包：PyInstaller onedir → 附上浏览器扩展、快捷脚本和说明 → VideoStudyGuardian-windows.zip

用法（在仓库根目录）：python windows/build.py
需要：Python 3.11+、pip install pyinstaller（可选 winsdk）
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = ROOT / "dist"
APP = DIST / "VideoStudyGuardian"
ZIP = DIST / "VideoStudyGuardian-windows.zip"

# 双击即可使用的快捷脚本（内容只用 ASCII，避免代码页问题）
SCRIPTS = {
    "家长控制面板.cmd": '@echo off\r\nstart "" "%~dp0VideoStudyGuardian.exe" --panel\r\n',
    "重新设置.cmd": '@echo off\r\nstart "" "%~dp0VideoStudyGuardian.exe" --setup\r\n',
}


def main():
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           "--distpath", str(DIST), "--workpath", str(ROOT / "build"),
                           str(HERE / "VideoStudyGuardian.spec")], cwd=ROOT)
    shutil.copytree(ROOT / "浏览器视频监控扩展", APP / "浏览器视频监控扩展", dirs_exist_ok=True)
    shutil.copy2(HERE / "README.md", APP / "使用说明.md")
    shutil.copy2(ROOT / "LICENSE", APP / "LICENSE.txt")
    for name, body in SCRIPTS.items():
        (APP / name).write_bytes(body.encode("ascii"))
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:  # 中文文件名使用 UTF-8 标记
        for path in sorted(APP.rglob("*")):
            zf.write(path, path.relative_to(DIST))
    print(f"built {ZIP} ({ZIP.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
