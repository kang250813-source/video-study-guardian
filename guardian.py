#!/usr/bin/env python3
"""本机视频学习守护：接收浏览器的视频心跳，并在时间用尽时覆盖整个屏幕（GTK3 版）。"""
import argparse
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import subprocess
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path.home() / ".config" / "video-study-guardian"
CONFIG_FILE = Path(os.environ.get("VSG_CONFIG", APP_DIR / "config.json"))
HOST, PORT = "127.0.0.1", int(os.environ.get("VSG_PORT", "8167"))
WRONG_WAIT = 3  # 答错后需等待的秒数，防止乱点


def normalize(value):
    """比较填空答案：忽略空格、大小写、全角/半角、弯引号。"""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    for a, b in (("’", "'"), ("‘", "'"), ("…", "."), ("：", ":")):
        text = text.replace(a, b)
    return re.sub(r"\s+", "", text)


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return salt.hex(), digest.hex()


def check_password(config, password):
    _, candidate = hash_password(password, bytes.fromhex(config["salt"]))
    return hmac.compare_digest(candidate, config["password_hash"])


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("尚未设置管理员密码。请先运行：python3 guardian.py --setup")


def setup():
    import getpass
    print("视频学习守护：首次设置管理员密码")
    password = getpass.getpass("设置管理员密码（至少6位）：")
    if len(password) < 6:
        raise SystemExit("密码至少需要 6 位，未保存任何设置。")
    if password != getpass.getpass("再次输入管理员密码："):
        raise SystemExit("两次密码不一致，未保存任何设置。")
    raw_minutes = input("每轮观看分钟数（直接回车为10）：").strip() or "10"
    try:
        minutes = max(1, min(60, int(raw_minutes)))
    except ValueError:
        raise SystemExit("分钟数必须是 1 到 60 的整数。")
    raw_grade = input("孩子读几年级？（1-6，直接回车为6）：").strip() or "6"
    if raw_grade not in {"1", "2", "3", "4", "5", "6"}:
        raise SystemExit("年级必须是 1 到 6。")
    default_term = "上" if time.localtime().tm_mon >= 8 or time.localtime().tm_mon == 1 else "下"
    term = input(f"上册还是下册？（上/下，直接回车为{default_term}）：").strip() or default_term
    if term not in {"上", "下"}:
        raise SystemExit("请输入“上”或“下”。")
    salt, digest = hash_password(password)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(APP_DIR, 0o700)
    CONFIG_FILE.write_text(json.dumps({"salt": salt, "password_hash": digest, "minutes": minutes,
                                       "grade": int(raw_grade), "term": term, "mode": "全部",
                                       "subjects": ["语文", "数学", "英语"]}, ensure_ascii=False), encoding="utf-8")
    os.chmod(CONFIG_FILE, 0o600)
    print(f"设置完成：每轮 {minutes} 分钟，{raw_grade} 年级{term}册。以后可在家长控制面板里修改。")


# ───────────────────────── 界面样式 ─────────────────────────
CSS = b"""
* { font-family: "Noto Sans CJK SC", "WenQuanYi Zen Hei", sans-serif; }
#lockwin { background-image: linear-gradient(135deg, #1b1840 0%, #2c2266 55%, #3d2a7a 100%); }
#card { background-color: rgba(255,255,255,0.97); border-radius: 28px; padding: 44px 56px; box-shadow: 0 20px 60px rgba(0,0,0,0.45); }
#eyebrow { color: #7a5cff; font-size: 17px; font-weight: 700; letter-spacing: 2px; }
#title { color: #24204a; font-size: 34px; font-weight: 800; }
#subject { color: white; font-size: 15px; font-weight: 700; border-radius: 999px; padding: 4px 16px; }
#subject.en { background-color: #2f9e72; }
#subject.math { background-color: #3a7bd5; }
#subject.cn { background-color: #e0703a; }
#question { color: #1f1b3d; font-size: 30px; font-weight: 600; }
.option { background-image: none; background-color: #f2efff; color: #2a2357; border: 2px solid #ddd5ff; border-radius: 16px; padding: 18px 22px; font-size: 24px; font-weight: 600; }
.option:hover { background-color: #e6e0ff; border-color: #a996ff; }
.option label { font-size: 24px; }
.option.right { background-color: #d9f7e8; border-color: #2f9e72; color: #1d6b4a; }
.option.wrong { background-color: #ffe1e1; border-color: #d94a4a; color: #a12b2b; }
.option:disabled { opacity: 0.85; }
#answer, #password { font-size: 26px; padding: 12px 18px; border-radius: 14px; min-width: 420px; }
.primary { background-image: none; background-color: #ffd23f; color: #231f40; border: none; border-radius: 14px; padding: 12px 34px; font-size: 22px; font-weight: 800; }
.primary:hover { background-color: #ffc400; }
.ghost { background-image: none; background-color: transparent; border: none; color: #8a83b0; font-size: 15px; box-shadow: none; }
.ghost:hover { color: #5b4ad8; }
#feedback { font-size: 20px; font-weight: 700; color: #c43c3c; }
#feedback.ok { color: #2f9e72; }
#hint { color: #8a83b0; font-size: 15px; }
#progress { color: #7a5cff; font-size: 18px; font-weight: 700; }
"""


def run_gui(guardian):
    os.environ.setdefault("GDK_BACKEND", "x11")  # 走 XWayland，才能可靠置顶
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk, GLib

    import questions

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    class LockWindow(Gtk.Window):
        def __init__(self):
            super().__init__(title="视频学习守护")
            self.set_name("lockwin")
            self.set_decorated(False)
            self.set_keep_above(True)
            self.set_skip_taskbar_hint(True)
            self.set_skip_pager_hint(True)
            self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            screen = Gdk.Screen.get_default()
            self.set_default_size(screen.get_width(), screen.get_height())
            self.move(0, 0)
            self.connect("delete-event", lambda *_: True)
            self.connect("key-press-event", self.on_key)
            self.recent = []
            self.question = None
            self.waiting = False
            self.need = 1  # 还需答对的题数；答错一题 +1

            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            outer.set_valign(Gtk.Align.CENTER)
            outer.set_halign(Gtk.Align.CENTER)
            self.add(outer)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            card.set_name("card")
            card.set_size_request(860, -1)
            outer.pack_start(card, False, False, 0)

            self.stack = Gtk.Stack()
            self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            card.pack_start(self.stack, True, True, 0)

            # 答题页
            quiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            eyebrow = Gtk.Label(label="✦ 视频时间到了 ✦"); eyebrow.set_name("eyebrow")
            title = Gtk.Label(label="认真答题，答对就能继续观看"); title.set_name("title")
            quiz.pack_start(eyebrow, False, False, 0)
            quiz.pack_start(title, False, False, 0)
            self.progress = Gtk.Label(); self.progress.set_name("progress")
            quiz.pack_start(self.progress, False, False, 0)
            self.subject = Gtk.Label(); self.subject.set_name("subject"); self.subject.set_halign(Gtk.Align.CENTER)
            quiz.pack_start(self.subject, False, False, 10)
            self.prompt = Gtk.Label(); self.prompt.set_name("question")
            self.prompt.set_line_wrap(True); self.prompt.set_max_width_chars(30); self.prompt.set_justify(Gtk.Justification.CENTER)
            quiz.pack_start(self.prompt, False, False, 6)

            self.options = Gtk.Grid(column_spacing=16, row_spacing=16, column_homogeneous=True)
            self.option_buttons = []
            for i in range(4):
                b = Gtk.Button(); b.get_style_context().add_class("option")
                lbl = Gtk.Label(); lbl.set_line_wrap(True); lbl.set_xalign(0)
                b.add(lbl)
                b.connect("clicked", self.on_option, i)
                self.options.attach(b, i % 2, i // 2, 1, 1)
                self.option_buttons.append(b)
            quiz.pack_start(self.options, False, False, 4)

            self.fillbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self.answer = Gtk.Entry(); self.answer.set_name("answer"); self.answer.set_alignment(0.5)
            self.answer.set_halign(Gtk.Align.CENTER)
            self.answer.connect("activate", self.on_fill)
            submit = Gtk.Button(label="提交答案"); submit.get_style_context().add_class("primary"); submit.set_halign(Gtk.Align.CENTER)
            submit.connect("clicked", self.on_fill)
            self.fillbox.pack_start(self.answer, False, False, 0)
            self.fillbox.pack_start(submit, False, False, 0)
            quiz.pack_start(self.fillbox, False, False, 4)

            self.feedback = Gtk.Label(label=""); self.feedback.set_name("feedback")
            quiz.pack_start(self.feedback, False, False, 4)
            admin_btn = Gtk.Button(label="管理员解锁"); admin_btn.get_style_context().add_class("ghost"); admin_btn.set_halign(Gtk.Align.CENTER)
            admin_btn.connect("clicked", lambda *_: self.show_admin())
            quiz.pack_start(admin_btn, False, False, 0)
            self.stack.add_named(quiz, "quiz")

            # 管理员页（同一窗口内，不再弹出会被挡住的小窗）
            admin = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
            t = Gtk.Label(label="管理员解锁"); t.set_name("title")
            h = Gtk.Label(label="输入管理员密码后按回车"); h.set_name("hint")
            self.password = Gtk.Entry(); self.password.set_name("password"); self.password.set_visibility(False)
            self.password.set_alignment(0.5); self.password.set_halign(Gtk.Align.CENTER)
            self.password.connect("activate", self.on_password)
            self.admin_msg = Gtk.Label(label=""); self.admin_msg.set_name("feedback")
            row = Gtk.Box(spacing=14); row.set_halign(Gtk.Align.CENTER)
            ok = Gtk.Button(label="解锁"); ok.get_style_context().add_class("primary"); ok.connect("clicked", self.on_password)
            back = Gtk.Button(label="返回答题"); back.get_style_context().add_class("ghost"); back.connect("clicked", lambda *_: self.show_quiz())
            row.pack_start(ok, False, False, 0); row.pack_start(back, False, False, 0)
            for w in (t, h, self.password, self.admin_msg, row):
                admin.pack_start(w, False, False, 0)
            self.stack.add_named(admin, "admin")

        # ── 题目 ──
        def next_question(self):
            allq = [questions.to_tuple(x) for x in questions.pool(guardian.config)]
            if not allq:
                allq = [("fill", "数学", "题库是空的，请家长检查 bank 文件夹。临时题：3 + 4 = ?", ["7"])]
            pool = [q for q in allq if q[2] not in self.recent] or allq
            # 先随机选科目，再选题，避免题量多的科目（如英语单词）占满
            subject = random.choice(sorted({x[1] for x in pool}))
            q = random.choice([x for x in pool if x[1] == subject])
            self.recent = (self.recent + [q[2]])[-30:]
            if q[0] == "choice":
                _, subject, prompt, opts, right = q
                order = list(range(len(opts))); random.shuffle(order)
                self.question = ("choice", subject, prompt, [opts[i] for i in order], order.index(right))
            else:
                self.question = q
            kind, subject = self.question[0], self.question[1]
            ctx = self.subject.get_style_context()
            for s in ("en", "math", "cn"):
                ctx.remove_class(s)
            ctx.add_class({"英语": "en", "数学": "math", "语文": "cn"}.get(subject, "cn"))
            self.subject.set_text(subject)
            self.prompt.set_text(self.question[2])
            if kind == "choice":
                for i, b in enumerate(self.option_buttons):
                    c = b.get_style_context(); c.remove_class("right"); c.remove_class("wrong")
                    b.get_child().set_text(f"{'ABCD'[i]}.  {self.question[3][i]}")
                    b.set_sensitive(True)
                self.options.show(); self.fillbox.hide()
            else:
                self.answer.set_text(""); self.answer.set_sensitive(True)
                self.options.hide(); self.fillbox.show(); self.answer.grab_focus()

        def on_option(self, _btn, index):
            if self.waiting or not self.question or self.question[0] != "choice":
                return
            right = self.question[4]
            for b in self.option_buttons:
                b.set_sensitive(False)
            if index == right:
                self.option_buttons[index].get_style_context().add_class("right")
                self.correct()
            else:
                self.option_buttons[index].get_style_context().add_class("wrong")
                self.option_buttons[right].get_style_context().add_class("right")
                self.wrong()

        def on_fill(self, *_):
            if self.waiting or not self.question or self.question[0] != "fill":
                return
            if normalize(self.answer.get_text()) in {normalize(v) for v in self.question[3]}:
                self.answer.set_sensitive(False)
                self.correct()
            else:
                self.answer.set_sensitive(False)
                self.wrong(f"正确答案：{self.question[3][0]}")

        def update_progress(self):
            self.progress.set_text(f"还需答对 {self.need} 题" + ("（答错一题会多加一题）" if self.need == 1 else ""))

        def correct(self):
            fc = self.feedback.get_style_context(); fc.add_class("ok")
            self.need -= 1
            self.waiting = True
            if self.need <= 0:
                self.feedback.set_text("答对了！马上解锁～")
                GLib.timeout_add(900, lambda: (guardian.unlock(), False)[1])
                return
            self.feedback.set_text(f"答对了！还要再答对 {self.need} 题")
            def go():
                self.waiting = False
                fc.remove_class("ok"); self.feedback.set_text("")
                self.update_progress(); self.next_question()
                return False
            GLib.timeout_add(1200, go)

        def wrong(self, extra=""):
            self.feedback.get_style_context().remove_class("ok")
            self.need += 1
            self.update_progress()
            self.waiting = True
            left = [WRONG_WAIT]
            def countdown():
                if left[0] <= 0:
                    self.waiting = False
                    self.feedback.set_text("")
                    self.next_question()
                    return False
                msg = "答错了，多加一题。看看正确答案，" if not extra else f"答错了，多加一题。{extra}，"
                self.feedback.set_text(f"{msg}{left[0]} 秒后换一道题")
                left[0] -= 1
                return True
            countdown(); GLib.timeout_add(1000, countdown)

        # ── 管理员 ──
        def show_admin(self):
            self.password.set_text(""); self.admin_msg.set_text("")
            self.stack.set_visible_child_name("admin")
            self.password.grab_focus()

        def show_quiz(self):
            self.stack.set_visible_child_name("quiz")
            if self.question and self.question[0] == "fill":
                self.answer.grab_focus()

        def on_password(self, *_):
            if check_password(guardian.config, self.password.get_text()):
                guardian.unlock()
            else:
                self.admin_msg.set_text("密码不正确")
                self.password.set_text(""); self.password.grab_focus()

        def on_key(self, _w, event):
            # 屏蔽 Esc、Alt+F4、Ctrl+Q、Ctrl+W
            if event.keyval == Gdk.KEY_Escape:
                if self.stack.get_visible_child_name() == "admin":
                    self.show_quiz()
                return True
            mods = event.state
            if mods & Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_F4:
                return True
            if mods & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_q, Gdk.KEY_w):
                return True
            return False

        def open(self):
            self.feedback.set_text(""); self.waiting = False
            self.feedback.get_style_context().remove_class("ok")
            self.need = 1; self.update_progress()
            self.stack.set_visible_child_name("quiz")
            self.show_all()
            self.next_question()
            self.fullscreen()
            self.present()
            GLib.timeout_add(400, self.keep_front)

        def keep_front(self):
            """被别的窗口盖住时重新置顶；只抢窗口焦点，不抢框内光标，避免打断输入密码。"""
            if not self.get_visible():
                return False
            if not self.is_active():
                self.set_keep_above(True)
                self.present()
            return True

    win = LockWindow()

    def apply_events():
        if guardian.locked and not win.get_visible():
            win.open()
        elif not guardian.locked and win.get_visible():
            win.hide()
        return True

    guardian.notify = lambda: GLib.idle_add(apply_events)
    GLib.timeout_add(1000, lambda: (guardian.tick(), apply_events())[1])
    Gtk.main()


class Guardian:
    def __init__(self, config):
        self.config = config
        self.round_seconds = config["minutes"] * 60
        self.remaining = float(self.round_seconds)
        self.last_activity = 0.0
        self.last_tick = time.monotonic()
        self.locked = False
        self.lock = threading.Lock()
        self.notify = lambda: None
        self.config_mtime = self._mtime()

    @property
    def work_mode(self):
        return bool(self.config.get("work_mode"))

    @staticmethod
    def _mtime():
        try:
            return CONFIG_FILE.stat().st_mtime
        except OSError:
            return 0

    def reload_config(self):
        """家长面板改了时长、密码或工作模式后，无需重启即可生效。"""
        mtime = self._mtime()
        if mtime == self.config_mtime:
            return
        self.config_mtime = mtime
        try:
            new = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        unlock = False
        with self.lock:
            minutes_changed = new.get("minutes") != self.config.get("minutes")
            self.config = new
            self.round_seconds = new["minutes"] * 60
            if minutes_changed:
                self.remaining = float(self.round_seconds)
            if self.work_mode and self.locked:
                unlock = True
        if unlock:
            self.unlock()

    def snapshot(self):
        return {"remaining": int(round(self.remaining)), "locked": self.locked, "minutes": self.config["minutes"], "work_mode": self.work_mode}

    def status(self):
        with self.lock:
            return self.snapshot()

    def activity(self):
        with self.lock:
            if not self.locked:
                self.last_activity = time.monotonic()
            return self.snapshot()

    def tick(self):
        self.reload_config()
        now = time.monotonic()
        elapsed = now - self.last_tick
        self.last_tick = now
        newly_locked = False
        with self.lock:
            if not self.locked and not self.work_mode and now - self.last_activity < 7:
                self.remaining = max(0.0, self.remaining - elapsed)
                if self.remaining <= 0:
                    self.locked = newly_locked = True
        if newly_locked:
            threading.Thread(target=pause_all_players, daemon=True).start()

    def force_lock(self):
        if self.work_mode:
            return self.status()
        with self.lock:
            if not self.locked:
                self.remaining = 0.0
                self.locked = True
        threading.Thread(target=pause_all_players, daemon=True).start()
        self.notify()
        return self.status()

    def unlock(self):
        with self.lock:
            self.locked = False
            self.remaining = float(self.round_seconds)
            self.last_activity = 0.0
        self.notify()


class Handler(BaseHTTPRequestHandler):
    guardian = None

    def log_message(self, *_):
        pass

    def send_json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self.send_json(self.guardian.status())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/activity":
            self.send_json(self.guardian.activity())
        elif self.path == "/lock":
            self.send_json(self.guardian.force_lock())
        else:
            self.send_error(404)


VIDEO_PLAYERS = ("chrome", "chromium", "firefox", "brave", "edge", "vivaldi", "vlc", "mpv", "totem", "celluloid")


def _gdbus(*args):
    try:
        return subprocess.run(["gdbus", *args], capture_output=True, text=True, timeout=2, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def video_players():
    names = _gdbus("call", "--session", "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames")
    return [n for n in re.findall(r"org\.mpris\.MediaPlayer2\.[A-Za-z0-9_.-]+", names) if any(p in n.lower() for p in VIDEO_PLAYERS)]


def is_playing(name):
    status = _gdbus("call", "--session", "--dest", name, "--object-path", "/org/mpris/MediaPlayer2", "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player", "PlaybackStatus")
    return "Playing" in status


def pause_all_players():
    for name in video_players():
        _gdbus("call", "--session", "--dest", name, "--object-path", "/org/mpris/MediaPlayer2", "--method", "org.mpris.MediaPlayer2.Player.Pause")


class MediaWatcher(threading.Thread):
    """监听 MPRIS 媒体会话：计时补充；锁定期间如有视频在播就暂停它。"""

    def __init__(self, guardian):
        super().__init__(daemon=True)
        self.guardian = guardian

    def run(self):
        while True:
            playing = [n for n in video_players() if is_playing(n)]
            if playing and not self.guardian.work_mode:
                if self.guardian.locked:
                    pause_all_players()
                else:
                    self.guardian.activity()
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    args = parser.parse_args()
    if args.setup:
        setup(); return
    guardian = Guardian(load_config())
    Handler.guardian = guardian
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    MediaWatcher(guardian).start()
    run_gui(guardian)


if __name__ == "__main__":
    main()
