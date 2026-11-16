#!/usr/bin/env python3
"""视频学习守护的家长控制面板（GTK3 版）。"""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from guardian import hash_password, check_password
import questions

APP_DIR = Path.home() / ".config" / "video-study-guardian"
CONFIG = APP_DIR / "config.json"
SERVICE = "video-study-guardian.service"

CSS = b"""
* { font-family: "Noto Sans CJK SC", "WenQuanYi Zen Hei", sans-serif; }
#panel { background-color: #f5f3ff; }
#card { background-color: white; border-radius: 22px; padding: 30px 36px; }
#title { color: #3c327d; font-size: 26px; font-weight: 800; }
#sub { color: #756e93; font-size: 14px; }
#status { font-size: 15px; font-weight: 700; }
#status.ok { color: #26734c; }
#status.bad { color: #a33d4e; }
.big { font-size: 16px; }
.btn { background-image: none; color: white; border: none; border-radius: 12px; padding: 10px; font-size: 15px; font-weight: 700; }
.purple { background-color: #513dc0; }
.violet { background-color: #6a4fd2; }
.slate { background-color: #4d4880; }
.green { background-color: #25734c; }
.red { background-color: #a33d4e; }
.work { background-color: #c98a12; }
#status.work { color: #b37400; }
.btn:hover { opacity: 0.9; }
"""


def load():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save(data):
    CONFIG.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.chmod(CONFIG, 0o600)


def request(path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:8167{path}", method=method)
    with urllib.request.urlopen(req, timeout=2) as result:
        return json.loads(result.read())


class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title="视频学习守护 · 家长控制")
        self.set_name("panel")
        self.set_resizable(False)
        self.set_border_width(18)
        self.connect("destroy", Gtk.main_quit)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.set_name("card")
        self.add(card)

        t = Gtk.Label(label="✦ 视频学习守护"); t.set_name("title")
        s = Gtk.Label(label="家长控制面板"); s.set_name("sub")
        self.status = Gtk.Label(); self.status.set_name("status")
        for w in (t, s, self.status):
            card.pack_start(w, False, False, 2)

        row = Gtk.Box(spacing=8); row.set_halign(Gtk.Align.CENTER)
        l1 = Gtk.Label(label="每轮观看"); l1.get_style_context().add_class("big")
        self.minutes = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.minutes.set_value(load()["minutes"])
        l2 = Gtk.Label(label="分钟"); l2.get_style_context().add_class("big")
        for w in (l1, self.minutes, l2):
            row.pack_start(w, False, False, 0)
        card.pack_start(row, False, False, 6)

        st = questions.settings(load())
        grid = Gtk.Grid(column_spacing=10, row_spacing=8); grid.set_halign(Gtk.Align.CENTER)
        def combo(items, active):
            c = Gtk.ComboBoxText()
            for it in items:
                c.append_text(it)
            c.set_active(items.index(active) if active in items else 0)
            return c
        self.grades = [f"{n} 年级" for n in range(1, 7)]
        self.grade = combo(self.grades, f"{st['grade']} 年级")
        self.term = combo(["上册", "下册"], f"{st['term']}册")
        self.mode = combo(list(questions.MODES), st["mode"])
        self.edition = combo(["新版", "旧版"], "旧版" if st["english_edition"] == "old" else "新版")
        subj = Gtk.Box(spacing=8)
        self.subject_checks = {}
        for name in questions.SUBJECT_DIRS:
            cb = Gtk.CheckButton(label=name); cb.set_active(name in st["subjects"])
            self.subject_checks[name] = cb; subj.pack_start(cb, False, False, 0)
        for i, (label, widget) in enumerate((("年级", self.grade), ("课本", self.term), ("科目", subj),
                                             ("专题", self.mode), ("英语课本", self.edition))):
            l = Gtk.Label(label=label); l.set_xalign(1); l.get_style_context().add_class("big")
            grid.attach(l, 0, i, 1, 1); grid.attach(widget, 1, i, 1, 1)
        card.pack_start(grid, False, False, 6)

        for label, color, cb in (
            ("保存设置", "purple", self.save_minutes),
            ("立即全屏锁定（测试）", "violet", self.lock_now),
            (None, "work", self.toggle_work),
            ("修改管理员密码", "slate", self.change_password),
            ("启动守护", "green", lambda *_: self.service("start")),
            ("停止守护", "red", lambda *_: self.service("stop")),
        ):
            b = Gtk.Button(label=label or "")
            b.get_style_context().add_class("btn"); b.get_style_context().add_class(color)
            b.connect("clicked", cb)
            card.pack_start(b, False, False, 3)
            if color == "work":
                self.work_button = b
        tip = Gtk.Label(label="观看网页视频满时长后，会出现全屏答题锁。"); tip.set_name("sub")
        card.pack_start(tip, False, False, 10)
        self.refresh()
        GLib.timeout_add(2000, self.refresh)

    def message(self, kind, title, text):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=kind, buttons=Gtk.ButtonsType.OK, text=title)
        d.format_secondary_text(text); d.run(); d.destroy()

    def ask_password(self, title, prompt):
        d = Gtk.Dialog(title=title, transient_for=self, modal=True)
        d.add_buttons("取消", Gtk.ResponseType.CANCEL, "确定", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        box = d.get_content_area(); box.set_spacing(10); box.set_border_width(16)
        box.add(Gtk.Label(label=prompt))
        e = Gtk.Entry(); e.set_visibility(False); e.set_activates_default(True)
        box.add(e); d.show_all()
        ok = d.run() == Gtk.ResponseType.OK
        value = e.get_text(); d.destroy()
        return value if ok else None

    def refresh(self):
        ctx = self.status.get_style_context(); ctx.remove_class("ok"); ctx.remove_class("bad"); ctx.remove_class("work")
        on = bool(load().get("work_mode"))
        self.work_button.set_label("关闭工作模式（恢复守护）" if on else "开启工作模式（不计时、不锁屏）")
        try:
            data = request("/status")
            if on:
                self.status.set_text("● 工作模式中：不计时、不锁屏"); ctx.add_class("work")
            elif data["locked"]:
                self.status.set_text("● 已锁定，等待答题或管理员解锁"); ctx.add_class("bad")
            else:
                r = data["remaining"]
                self.status.set_text(f"● 守护正在运行 · 还可观看 {r // 60:02d}:{r % 60:02d}"); ctx.add_class("ok")
        except Exception:
            self.status.set_text("● 守护未运行"); ctx.add_class("bad")
        return True

    def service(self, action):
        r = subprocess.run(["systemctl", "--user", action, SERVICE], text=True, capture_output=True)
        if r.returncode:
            self.message(Gtk.MessageType.ERROR, "操作失败", r.stderr.strip() or "无法操作守护服务")

    def save_minutes(self, *_):
        value = int(self.minutes.get_value())
        subjects = [n for n, cb in self.subject_checks.items() if cb.get_active()]
        if not subjects:
            self.message(Gtk.MessageType.ERROR, "未保存", "至少选择一个科目。"); return
        data = load()
        data.update(minutes=value, grade=self.grade.get_active() + 1, term="上" if self.term.get_active() == 0 else "下",
                    mode=self.mode.get_active_text(), subjects=subjects,
                    english_edition="old" if self.edition.get_active() == 1 else "new")
        save(data)  # 守护自动生效
        n = len(questions.pool(data))
        self.message(Gtk.MessageType.INFO, "已保存",
                     f"每轮 {value} 分钟，{data['grade']} 年级{data['term']}册，专题：{data['mode']}。当前可用题目 {n} 道。")

    def toggle_work(self, *_):
        data = load()
        if data.get("work_mode"):
            data["work_mode"] = False; save(data); self.refresh()
            self.message(Gtk.MessageType.INFO, "已关闭工作模式", "守护已恢复计时。")
            return
        pw = self.ask_password("开启工作模式", "请输入管理员密码：")
        if pw is None:
            return
        if not check_password(data, pw):
            self.message(Gtk.MessageType.ERROR, "验证失败", "管理员密码不正确。"); return
        data["work_mode"] = True; save(data); self.refresh()
        self.message(Gtk.MessageType.INFO, "已开启工作模式", "现在不会计时，也不会出现答题锁。用完记得关闭。")

    def lock_now(self, *_):
        try:
            request("/lock", "POST")
        except Exception:
            self.message(Gtk.MessageType.ERROR, "无法锁定", "守护未运行，请先点击“启动守护”。")

    def change_password(self, *_):
        old = self.ask_password("验证管理员", "请输入当前管理员密码：")
        if old is None:
            return
        data = load()
        if not check_password(data, old):
            self.message(Gtk.MessageType.ERROR, "验证失败", "当前管理员密码不正确。"); return
        new = self.ask_password("修改密码", "输入新管理员密码（至少 6 位）：")
        if new is None:
            return
        if len(new) < 6:
            self.message(Gtk.MessageType.ERROR, "设置错误", "密码至少为 6 位。"); return
        if new != self.ask_password("确认密码", "再输入一次新密码："):
            self.message(Gtk.MessageType.ERROR, "设置错误", "两次输入不一致。"); return
        data["salt"], data["password_hash"] = hash_password(new)
        save(data)  # 守护会自动读取新密码
        self.message(Gtk.MessageType.INFO, "已保存", "管理员密码已修改。")


if __name__ == "__main__":
    if not CONFIG.exists():
        raise SystemExit("请先运行 install.sh 设置管理员密码。")
    provider = Gtk.CssProvider(); provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    Panel().show_all()
    Gtk.main()
