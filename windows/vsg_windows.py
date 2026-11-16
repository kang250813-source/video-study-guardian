#!/usr/bin/env python3
"""视频学习守护 Windows 版入口。

  VideoStudyGuardian.exe              启动守护（首次运行先弹出设置；守护已在运行时打开家长面板）
  VideoStudyGuardian.exe --panel      家长控制面板（需要管理员密码）
  VideoStudyGuardian.exe --setup      重新设置（已有密码时需先输入旧密码）
  VideoStudyGuardian.exe --selftest [结果文件]   无界面自检：题库、配置、HTTP 接口（用于 CI）

源码运行：python windows\\vsg_windows.py [参数]
"""
import argparse
import os
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vsg_core as core  # noqa: E402
import vsg_winsys as winsys  # noqa: E402


def _log_crash(exc_type, exc, tb):
    try:
        core.app_dir().mkdir(parents=True, exist_ok=True)
        with open(core.app_dir() / "error.log", "a", encoding="utf-8") as fh:
            fh.write("".join(traceback.format_exception(exc_type, exc, tb)) + "\n")
    except OSError:
        pass


def selftest(out=None):
    """不打开任何窗口的自检，返回进程退出码（0 = 通过）。"""
    import json
    import tempfile
    import urllib.request

    lines, ok = [], True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        lines.append(f"{'PASS' if cond else 'FAIL'} {name} {detail}".rstrip())

    check("bank dir", (core.ROOT / "bank").is_dir(), str(core.questions.BANK_DIR))
    for grade in range(1, 7):
        for term in ("上", "下"):
            n = len(core.questions.pool({"grade": grade, "term": term}))
            check(f"pool g{grade}{term}", n > 0, str(n))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        cfg = core.new_config("secret123", 1, 3, "上")
        core.save_config(cfg, path)
        loaded = core.load_config(path)
        check("config roundtrip", loaded == cfg)
        check("password ok", core.check_password(loaded, "secret123"))
        check("password bad", not core.check_password(loaded, "wrong"))
        q = core.pick_question(loaded)
        check("pick question", q[0] in ("choice", "fill"), q[1])
        g = core.Guardian(loaded, config_path=path)
        server = core.make_server(g, port=0)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            st = core.request("/status", port=port)
            check("GET /status", set(st) == {"remaining", "locked", "minutes", "work_mode"}, json.dumps(st))
            check("POST /activity", core.request("/activity", "POST", port=port)["locked"] is False)
            check("POST /lock", core.request("/lock", "POST", port=port)["locked"] is True)
            req = urllib.request.Request(f"http://127.0.0.1:{port}/status", method="OPTIONS")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=2) as r:
                check("OPTIONS CORS", r.status == 204 and r.headers["Access-Control-Allow-Origin"] == "*")
        finally:
            server.shutdown()
            server.server_close()
    try:
        import vsg_media
        lines.append(f"INFO winsdk media sessions available: {vsg_media.AVAILABLE}")
    except Exception as exc:  # 媒体检测是可选的
        lines.append(f"INFO media module error: {exc!r}")
    report = "\n".join(lines) + f"\nRESULT {'OK' if ok else 'FAILED'}\n"
    if out:
        Path(out).write_text(report, encoding="utf-8")
    elif sys.stdout:
        try:
            sys.stdout.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
        sys.stdout.write(report)
    return 0 if ok else 1


def run_guardian():
    import vsg_gui as gui

    if not winsys.acquire_single_instance():
        gui.run_panel()  # 守护已在运行：再次双击就打开家长面板
        return
    config = core.load_config()
    if not config:
        if not gui.run_setup(require_old=False):
            return
        config = core.load_config()
        if not config:
            return
    guardian = core.Guardian(config)
    try:
        server = core.make_server(guardian)
    except OSError:
        gui.show_error(core.APP_TITLE, f"本机端口 {core.PORT} 已被占用，守护可能已经在运行。")
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        core.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        core.PID_FILE.write_text(str(os.getpid()))
    except OSError:
        pass
    try:
        import vsg_media
        watcher = vsg_media.MediaWatcher(guardian)
        guardian.on_lock = watcher.request_pause
        watcher.start()
    except Exception:
        pass  # 没有 winsdk 时只靠浏览器扩展计时
    gui.run_guardian(guardian)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="VideoStudyGuardian", description="视频学习守护 Windows 版")
    parser.add_argument("--panel", action="store_true", help="打开家长控制面板")
    parser.add_argument("--setup", action="store_true", help="重新设置管理员密码和年级")
    parser.add_argument("--selftest", nargs="?", const="", metavar="OUT", help="无界面自检")
    args = parser.parse_args(argv)
    if args.selftest is not None:
        return selftest(args.selftest or None)
    sys.excepthook = _log_crash
    winsys.enable_dpi_awareness()
    if args.panel:
        import vsg_gui
        vsg_gui.run_panel()
    elif args.setup:
        import vsg_gui
        vsg_gui.run_setup(require_old=True)
    else:
        run_guardian()
    return 0


if __name__ == "__main__":
    sys.exit(main())
