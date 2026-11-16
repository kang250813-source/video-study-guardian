"""视频学习守护 Windows 版界面（tkinter）：全屏答题锁、首次设置对话框、家长控制面板。"""
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import vsg_core as core
import vsg_winsys as winsys
from vsg_core import questions

FONT = "Microsoft YaHei UI"
BG = "#2c2266"
CARD = "#ffffff"
PURPLE = "#7a5cff"
INK = "#1f1b3d"
SUBJECT_COLORS = {"英语": "#2f9e72", "数学": "#3a7bd5", "语文": "#e0703a"}
OPTION_BG, OPTION_RIGHT, OPTION_WRONG = "#f2efff", "#d9f7e8", "#ffe1e1"


def new_root():
    """界面回调里的异常交给 sys.excepthook（入口里会写入 error.log）。"""
    root = tk.Tk()
    root.report_callback_exception = lambda *exc: sys.excepthook(*exc)
    return root


def f(size, bold=False):
    return (FONT, size, "bold") if bold else (FONT, size)


# ───────────────────────── 全屏答题锁 ─────────────────────────
class LockScreen:
    def __init__(self, root, guardian):
        self.root = root
        self.guardian = guardian
        self.quiz = core.QuizSession(lambda: self.guardian.config)
        self.blocker = winsys.KeyBlocker()
        self.waiting = False
        self.visible = False
        self._after_ids = []

        root.title(core.APP_TITLE)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", lambda: None)  # 忽略关闭 / Alt+F4
        root.bind("<Escape>", self.on_escape)
        root.bind("<Alt-F4>", lambda e: "break")

        self.card = tk.Frame(root, bg=CARD, padx=56, pady=40)
        # 答题页
        self.quiz_page = tk.Frame(self.card, bg=CARD)
        tk.Label(self.quiz_page, text="✦ 视频时间到了 ✦", fg=PURPLE, bg=CARD, font=f(15, True)).pack(pady=(0, 4))
        tk.Label(self.quiz_page, text="认真答题，答对就能继续观看", fg="#24204a", bg=CARD, font=f(26, True)).pack()
        self.progress = tk.Label(self.quiz_page, fg=PURPLE, bg=CARD, font=f(14, True))
        self.progress.pack(pady=(8, 0))
        self.subject = tk.Label(self.quiz_page, fg="white", bg="#e0703a", font=f(12, True), padx=16, pady=3)
        self.subject.pack(pady=12)
        self.prompt = tk.Label(self.quiz_page, fg=INK, bg=CARD, font=f(22, True), wraplength=760, justify="center")
        self.prompt.pack(pady=6)

        self.options = tk.Frame(self.quiz_page, bg=CARD)
        self.option_buttons = []
        for i in range(4):
            b = tk.Button(self.options, font=f(18, True), bg=OPTION_BG, fg="#2a2357", activebackground="#e6e0ff",
                          relief="flat", bd=0, padx=20, pady=16, wraplength=340, justify="left", anchor="w",
                          cursor="hand2", command=lambda i=i: self.on_option(i))
            b.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="nsew")
            self.option_buttons.append(b)
        self.options.grid_columnconfigure(0, weight=1, uniform="o")
        self.options.grid_columnconfigure(1, weight=1, uniform="o")

        self.fillbox = tk.Frame(self.quiz_page, bg=CARD)
        self.answer = tk.Entry(self.fillbox, font=f(22), justify="center", width=22, relief="solid", bd=1)
        self.answer.pack(pady=6, ipady=6)
        self.answer.bind("<Return>", lambda e: self.on_fill())
        self.primary(self.fillbox, "提交答案", self.on_fill).pack(pady=6)

        tk.Button(self.quiz_page, text="管理员解锁", font=f(11), fg="#8a83b0", bg=CARD, activebackground=CARD,
                  relief="flat", bd=0, cursor="hand2", command=self.show_admin).pack(side="bottom", pady=(6, 0))
        self.feedback = tk.Label(self.quiz_page, text="", fg="#c43c3c", bg=CARD, font=f(16, True), wraplength=760)
        self.feedback.pack(side="bottom", pady=(4, 0))

        # 管理员页（同一窗口内，不弹出会被挡住的小窗）
        self.admin_page = tk.Frame(self.card, bg=CARD)
        tk.Label(self.admin_page, text="管理员解锁", fg="#24204a", bg=CARD, font=f(26, True)).pack(pady=(0, 8))
        tk.Label(self.admin_page, text="输入管理员密码后按回车", fg="#8a83b0", bg=CARD, font=f(12)).pack()
        self.password = tk.Entry(self.admin_page, font=f(22), justify="center", width=22, show="●", relief="solid", bd=1)
        self.password.pack(pady=14, ipady=6)
        self.password.bind("<Return>", lambda e: self.on_password())
        self.admin_msg = tk.Label(self.admin_page, text="", fg="#c43c3c", bg=CARD, font=f(14, True))
        self.admin_msg.pack()
        row = tk.Frame(self.admin_page, bg=CARD)
        row.pack(pady=10)
        self.primary(row, "解锁", self.on_password).pack(side="left", padx=8)
        tk.Button(row, text="返回答题", font=f(12), fg="#8a83b0", bg=CARD, activebackground=CARD, relief="flat",
                  bd=0, cursor="hand2", command=self.show_quiz).pack(side="left", padx=8)

    @staticmethod
    def primary(parent, text, command):
        return tk.Button(parent, text=text, font=f(16, True), bg="#ffd23f", fg="#231f40", activebackground="#ffc400",
                         relief="flat", bd=0, padx=30, pady=8, cursor="hand2", command=command)

    def later(self, ms, fn):
        self._after_ids.append(self.root.after(ms, fn))

    def cancel_timers(self):
        for i in self._after_ids:
            try:
                self.root.after_cancel(i)
            except tk.TclError:
                pass
        self._after_ids.clear()

    # ── 出题 ──
    def update_progress(self):
        self.progress.config(text=f"还需答对 {self.quiz.need} 题" + ("（答错一题会多加一题）" if self.quiz.need == 1 else ""))

    def show_question(self, q):
        kind, subject = q[0], q[1]
        self.subject.config(text=subject, bg=SUBJECT_COLORS.get(subject, "#e0703a"))
        self.prompt.config(text=q[2])
        if kind == "choice":
            self.fillbox.pack_forget()
            self.options.pack(pady=4, fill="x")
            for i, b in enumerate(self.option_buttons):
                if i < len(q[3]):
                    b.config(text=f"{'ABCD'[i]}.  {q[3][i]}", bg=OPTION_BG, state="normal", disabledforeground="#6d6890")
                    b.grid()
                else:
                    b.grid_remove()
        else:
            self.options.pack_forget()
            self.fillbox.pack(pady=4)
            self.answer.config(state="normal")
            self.answer.delete(0, "end")
            self.answer.focus_set()

    def next_question(self):
        self.show_question(self.quiz.next())

    def on_option(self, index):
        q = self.quiz.question
        if self.waiting or not q or q[0] != "choice":
            return
        for b in self.option_buttons:
            b.config(state="disabled")
        ok, right = self.quiz.answer_choice(index)
        self.option_buttons[right].config(bg=OPTION_RIGHT, disabledforeground="#1d6b4a")
        if ok:
            self.correct()
        else:
            self.option_buttons[index].config(bg=OPTION_WRONG, disabledforeground="#a12b2b")
            self.wrong()

    def on_fill(self):
        q = self.quiz.question
        if self.waiting or not q or q[0] != "fill":
            return
        ok, expected = self.quiz.answer_fill(self.answer.get())
        self.answer.config(state="disabled")
        if ok:
            self.correct()
        else:
            self.wrong(f"正确答案：{expected}")

    def correct(self):
        self.waiting = True
        self.feedback.config(fg="#2f9e72")
        if self.quiz.done:
            self.feedback.config(text="答对了！马上解锁～")
            self.later(900, self.guardian.unlock)
            return
        self.feedback.config(text=f"答对了！还要再答对 {self.quiz.need} 题")

        def go():
            self.waiting = False
            self.feedback.config(text="", fg="#c43c3c")
            self.update_progress()
            self.next_question()
        self.later(1200, go)

    def wrong(self, extra=""):
        self.waiting = True
        self.feedback.config(fg="#c43c3c")
        self.update_progress()
        left = [core.WRONG_WAIT]
        msg = "答错了，多加一题。看看正确答案，" if not extra else f"答错了，多加一题。{extra}，"

        def countdown():
            if left[0] <= 0:
                self.waiting = False
                self.feedback.config(text="")
                self.next_question()
                return
            self.feedback.config(text=f"{msg}{left[0]} 秒后换一道题")
            left[0] -= 1
            self.later(1000, countdown)
        countdown()

    # ── 管理员 ──
    def show_admin(self):
        self.password.delete(0, "end")
        self.admin_msg.config(text="")
        self.quiz_page.pack_forget()
        self.admin_page.pack()
        self.password.focus_set()

    def show_quiz(self):
        self.admin_page.pack_forget()
        self.quiz_page.pack()
        q = self.quiz.question
        if q and q[0] == "fill":
            self.answer.focus_set()

    def on_escape(self, _event=None):
        if self.admin_page.winfo_ismapped():
            self.show_quiz()
        return "break"

    def on_password(self):
        if core.check_password(self.guardian.config, self.password.get()):
            self.guardian.unlock()
        else:
            self.admin_msg.config(text="密码不正确")
            self.password.delete(0, "end")
            self.password.focus_set()

    # ── 显示 / 隐藏 ──
    def place_fullscreen(self):
        vs = winsys.virtual_screen()
        if vs:  # Windows：覆盖所有显示器，题卡放在主显示器中央
            x, y, w, h = vs
            pw, ph = winsys.primary_screen()
            self.root.overrideredirect(True)
            self.root.geometry(f"{w}x{h}{x:+d}{y:+d}")
            self.card.place(x=-x + pw // 2, y=-y + ph // 2, anchor="center")
        else:
            self.root.attributes("-fullscreen", True)
            self.card.place(relx=0.5, rely=0.5, anchor="center")

    def open(self):
        self.cancel_timers()
        self.waiting = False
        self.feedback.config(text="", fg="#c43c3c")
        self.admin_page.pack_forget()
        self.quiz_page.pack()
        self.quiz.start()
        self.update_progress()
        self.show_question(self.quiz.question)
        self.place_fullscreen()
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        self.blocker.start()
        self.visible = True
        self.keep_front()

    def close(self):
        self.visible = False
        self.cancel_timers()
        self.blocker.stop()
        self.root.withdraw()

    def hwnd(self):
        try:
            return int(self.root.wm_frame(), 16)
        except (tk.TclError, ValueError):
            return None

    def keep_front(self):
        """被别的窗口盖住时重新置顶；只抢窗口焦点，不改框内光标，避免打断输入。"""
        if not self.visible:
            return
        self.root.attributes("-topmost", True)
        self.root.lift()
        if self.root.focus_get() is None:
            self.root.focus_force()
            winsys.force_foreground(self.hwnd())
        if not self.blocker.active:
            self.blocker.start()
        self.root.after(400, self.keep_front)


def run_guardian(guardian):
    root = new_root()
    root.withdraw()
    screen = LockScreen(root, guardian)

    def apply_state():
        if guardian.locked and not screen.visible:
            screen.open()
        elif not guardian.locked and screen.visible:
            screen.close()
        root.after(300, apply_state)

    def tick():
        try:
            guardian.tick()
        finally:
            root.after(1000, tick)

    root.after(300, apply_state)
    root.after(1000, tick)
    root.mainloop()


# ───────────────────────── 首次设置 ─────────────────────────
def run_setup(require_old=True):
    """显示设置对话框；保存成功返回 True。已有配置时需先验证旧密码，防止被孩子重置。"""
    existing = core.load_config()
    root = new_root()
    root.title(f"{core.APP_TITLE} · 首次设置")
    root.resizable(False, False)
    root.configure(bg="#f5f3ff")
    result = {"ok": False}

    if existing and require_old:
        root.withdraw()
        old = simpledialog.askstring("验证管理员", "已经设置过管理员密码。\n请输入当前管理员密码：", show="●", parent=root)
        if old is None or not core.check_password(existing, old):
            if old is not None:
                messagebox.showerror("验证失败", "管理员密码不正确。", parent=root)
            root.destroy()
            return False
        root.deiconify()

    frm = tk.Frame(root, bg="white", padx=30, pady=24)
    frm.pack(padx=18, pady=18)
    tk.Label(frm, text="✦ 视频学习守护", fg="#3c327d", bg="white", font=f(18, True)).grid(row=0, column=0, columnspan=2, pady=(0, 4))
    tk.Label(frm, text="设置家长使用的管理员密码和出题范围", fg="#756e93", bg="white", font=f(10)).grid(row=1, column=0, columnspan=2, pady=(0, 12))

    pw1, pw2 = tk.StringVar(), tk.StringVar()
    minutes = tk.StringVar(value=str(existing.get("minutes", 10)) if existing else "10")
    grade = tk.StringVar(value=f"{existing.get('grade', 6) if existing else 6} 年级")
    term = tk.StringVar(value=f"{(existing or {}).get('term') or core.default_term()}册")
    autostart = tk.BooleanVar(value=True)

    rows = (
        ("管理员密码（至少6位）", tk.Entry(frm, textvariable=pw1, show="●", width=24, font=f(11))),
        ("再次输入密码", tk.Entry(frm, textvariable=pw2, show="●", width=24, font=f(11))),
        ("每轮观看分钟数", tk.Spinbox(frm, from_=1, to=60, textvariable=minutes, width=6, font=f(11))),
        ("孩子的年级", ttk.Combobox(frm, textvariable=grade, values=[f"{n} 年级" for n in range(1, 7)], state="readonly", width=10)),
        ("上册 / 下册", ttk.Combobox(frm, textvariable=term, values=["上册", "下册"], state="readonly", width=10)),
    )
    for i, (label, widget) in enumerate(rows, start=2):
        tk.Label(frm, text=label, bg="white", font=f(11)).grid(row=i, column=0, sticky="e", padx=(0, 10), pady=5)
        widget.grid(row=i, column=1, sticky="w", pady=5)
    if winsys.IS_WINDOWS:
        tk.Checkbutton(frm, text="登录 Windows 时自动启动守护（当前用户）", variable=autostart, bg="white",
                       font=f(10)).grid(row=8, column=0, columnspan=2, pady=(8, 0))
    error = tk.Label(frm, text="", fg="#a33d4e", bg="white", font=f(10, True))
    error.grid(row=9, column=0, columnspan=2, pady=6)

    def save(*_):
        g, t = grade.get().split()[0], term.get()[0]
        problem = core.validate_setup(pw1.get(), pw2.get(), minutes.get(), g, t)
        if problem:
            error.config(text=problem)
            return
        data = core.new_config(pw1.get(), int(minutes.get()), int(g), t)
        if existing:  # 保留原来的科目、专题等设置
            for k in ("mode", "subjects", "english_edition"):
                if k in existing:
                    data[k] = existing[k]
        core.save_config(data)
        if winsys.IS_WINDOWS:
            try:
                winsys.set_autostart(autostart.get())
            except OSError:
                pass
        result["ok"] = True
        messagebox.showinfo("设置完成", f"每轮 {data['minutes']} 分钟，{g} 年级{t}册。\n以后可以在家长控制面板里修改。", parent=root)
        root.destroy()

    btns = tk.Frame(frm, bg="white")
    btns.grid(row=10, column=0, columnspan=2, pady=(4, 0))
    tk.Button(btns, text="保存", font=f(11, True), bg="#513dc0", fg="white", relief="flat", padx=24, pady=4,
              command=save).pack(side="left", padx=6)
    tk.Button(btns, text="取消", font=f(11), relief="flat", padx=16, pady=4, command=root.destroy).pack(side="left", padx=6)
    root.bind("<Return>", save)
    rows[0][1].focus_set()
    root.mainloop()
    return result["ok"]


# ───────────────────────── 家长控制面板 ─────────────────────────
class Panel:
    def __init__(self, root):
        self.root = root
        root.title(f"{core.APP_TITLE} · 家长控制")
        root.resizable(False, False)
        root.configure(bg="#f5f3ff")
        card = tk.Frame(root, bg="white", padx=30, pady=22)
        card.pack(padx=18, pady=18)

        tk.Label(card, text="✦ 视频学习守护", fg="#3c327d", bg="white", font=f(20, True)).pack()
        tk.Label(card, text="家长控制面板", fg="#756e93", bg="white", font=f(10)).pack()
        self.status = tk.Label(card, bg="white", font=f(11, True))
        self.status.pack(pady=6)

        data = core.load_config()
        st = questions.settings(data)
        row = tk.Frame(card, bg="white")
        row.pack(pady=4)
        tk.Label(row, text="每轮观看", bg="white", font=f(12)).pack(side="left")
        self.minutes = tk.Spinbox(row, from_=1, to=60, width=5, font=f(12))
        self.minutes.delete(0, "end")
        self.minutes.insert(0, str(data["minutes"]))
        self.minutes.pack(side="left", padx=6)
        tk.Label(row, text="分钟", bg="white", font=f(12)).pack(side="left")

        grid = tk.Frame(card, bg="white")
        grid.pack(pady=6)
        self.grade = tk.StringVar(value=f"{st['grade']} 年级")
        self.term = tk.StringVar(value=f"{st['term']}册")
        self.mode = tk.StringVar(value=st["mode"] if st["mode"] in questions.MODES else "全部")
        self.edition = tk.StringVar(value="旧版" if st["english_edition"] == "old" else "新版")
        subj = tk.Frame(grid, bg="white")
        self.subject_vars = {}
        for name in questions.SUBJECT_DIRS:
            v = tk.BooleanVar(value=name in st["subjects"])
            tk.Checkbutton(subj, text=name, variable=v, bg="white", font=f(11)).pack(side="left")
            self.subject_vars[name] = v

        def combo(var, values):
            return ttk.Combobox(grid, textvariable=var, values=values, state="readonly", width=10)
        for i, (label, widget) in enumerate((
                ("年级", combo(self.grade, [f"{n} 年级" for n in range(1, 7)])),
                ("课本", combo(self.term, ["上册", "下册"])),
                ("科目", subj),
                ("专题", combo(self.mode, list(questions.MODES))),
                ("英语课本", combo(self.edition, ["新版", "旧版"])))):
            tk.Label(grid, text=label, bg="white", font=f(11)).grid(row=i, column=0, sticky="e", padx=(0, 10), pady=4)
            widget.grid(row=i, column=1, sticky="w", pady=4)

        def button(text, color, command):
            b = tk.Button(card, text=text, bg=color, fg="white", activebackground=color, activeforeground="white",
                          font=f(11, True), relief="flat", bd=0, pady=8, cursor="hand2", command=command)
            b.pack(fill="x", pady=3)
            return b
        button("保存设置", "#513dc0", self.save_settings)
        button("立即全屏锁定（测试）", "#6a4fd2", self.lock_now)
        self.work_button = button("", "#c98a12", self.toggle_work)
        button("修改管理员密码", "#4d4880", self.change_password)
        button("启动守护", "#25734c", self.start_guardian)
        button("停止守护", "#a33d4e", self.stop_guardian)
        self.autostart = tk.BooleanVar(value=winsys.autostart_enabled())
        tk.Checkbutton(card, text="登录 Windows 时自动启动守护（仅当前用户）", variable=self.autostart, bg="white",
                       font=f(10), command=self.toggle_autostart).pack(pady=(8, 0))
        tk.Label(card, text="观看网页视频满时长后，会出现全屏答题锁。", fg="#756e93", bg="white", font=f(10)).pack(pady=(8, 0))
        self.refresh()

    def refresh(self):
        data = core.load_config() or {}
        on = bool(data.get("work_mode"))
        self.work_button.config(text="关闭工作模式（恢复守护）" if on else "开启工作模式（不计时、不锁屏）")
        try:
            s = core.request("/status")
            if on:
                text, color = "● 工作模式中：不计时、不锁屏", "#b37400"
            elif s["locked"]:
                text, color = "● 已锁定，等待答题或管理员解锁", "#a33d4e"
            else:
                r = s["remaining"]
                text, color = f"● 守护正在运行 · 还可观看 {r // 60:02d}:{r % 60:02d}", "#26734c"
        except Exception:
            text, color = "● 守护未运行", "#a33d4e"
        self.status.config(text=text, fg=color)
        self.root.after(2000, self.refresh)

    def save_settings(self):
        try:
            minutes = int(self.minutes.get())
            assert 1 <= minutes <= 60
        except (ValueError, AssertionError):
            messagebox.showerror("未保存", "分钟数必须是 1 到 60 的整数。", parent=self.root)
            return
        subjects = [n for n, v in self.subject_vars.items() if v.get()]
        if not subjects:
            messagebox.showerror("未保存", "至少选择一个科目。", parent=self.root)
            return
        data = core.load_config()
        data.update(minutes=minutes, grade=int(self.grade.get().split()[0]), term=self.term.get()[0],
                    mode=self.mode.get(), subjects=subjects,
                    english_edition="old" if self.edition.get() == "旧版" else "new")
        core.save_config(data)  # 守护会自动读取
        n = len(questions.pool(data))
        messagebox.showinfo("已保存", f"每轮 {minutes} 分钟，{data['grade']} 年级{data['term']}册，专题：{data['mode']}。"
                                    f"当前可用题目 {n} 道。", parent=self.root)

    def ask_password(self, title, prompt):
        return simpledialog.askstring(title, prompt, show="●", parent=self.root)

    def toggle_work(self):
        data = core.load_config()
        if data.get("work_mode"):
            data["work_mode"] = False
            core.save_config(data)
            messagebox.showinfo("已关闭工作模式", "守护已恢复计时。", parent=self.root)
            return
        pw = self.ask_password("开启工作模式", "请输入管理员密码：")
        if pw is None:
            return
        if not core.check_password(data, pw):
            messagebox.showerror("验证失败", "管理员密码不正确。", parent=self.root)
            return
        data["work_mode"] = True
        core.save_config(data)
        messagebox.showinfo("已开启工作模式", "现在不会计时，也不会出现答题锁。用完记得关闭。", parent=self.root)

    def lock_now(self):
        try:
            core.request("/lock", "POST")
        except Exception:
            messagebox.showerror("无法锁定", "守护未运行，请先点击“启动守护”。", parent=self.root)

    def change_password(self):
        old = self.ask_password("验证管理员", "请输入当前管理员密码：")
        if old is None:
            return
        data = core.load_config()
        if not core.check_password(data, old):
            messagebox.showerror("验证失败", "当前管理员密码不正确。", parent=self.root)
            return
        new = self.ask_password("修改密码", "输入新管理员密码（至少 6 位）：")
        if new is None:
            return
        if len(new) < 6:
            messagebox.showerror("设置错误", "密码至少为 6 位。", parent=self.root)
            return
        if new != self.ask_password("确认密码", "再输入一次新密码："):
            messagebox.showerror("设置错误", "两次输入不一致。", parent=self.root)
            return
        data["salt"], data["password_hash"] = core.hash_password(new)
        core.save_config(data)
        messagebox.showinfo("已保存", "管理员密码已修改。", parent=self.root)

    def start_guardian(self):
        if winsys.guardian_running():
            messagebox.showinfo("守护", "守护已经在运行。", parent=self.root)
            return
        try:
            winsys.launch_guardian()
        except OSError as exc:
            messagebox.showerror("启动失败", str(exc), parent=self.root)

    def stop_guardian(self):
        if not winsys.guardian_running():
            messagebox.showinfo("守护", "守护没有在运行。", parent=self.root)
            return
        if not messagebox.askyesno("停止守护", "确定停止守护吗？停止后不再计时和锁屏，直到再次启动或重新登录。", parent=self.root):
            return
        if not winsys.stop_guardian(core.PID_FILE):
            messagebox.showerror("操作失败", "无法停止守护进程。", parent=self.root)

    def toggle_autostart(self):
        try:
            self.autostart.set(winsys.set_autostart(self.autostart.get()))
        except OSError as exc:
            messagebox.showerror("操作失败", str(exc), parent=self.root)
            self.autostart.set(winsys.autostart_enabled())


def run_panel():
    data = core.load_config()
    root = new_root()
    root.withdraw()
    if not data:
        messagebox.showerror(core.APP_TITLE, "尚未完成首次设置，请先运行“视频学习守护”。", parent=root)
        root.destroy()
        return
    pw = simpledialog.askstring("家长控制面板", "请输入管理员密码：", show="●", parent=root)
    if pw is None:
        root.destroy()
        return
    if not core.check_password(data, pw):
        messagebox.showerror("验证失败", "管理员密码不正确。", parent=root)
        root.destroy()
        return
    Panel(root)
    root.deiconify()
    root.mainloop()


def show_error(title, text):
    root = new_root()
    root.withdraw()
    messagebox.showerror(title, text, parent=root)
    root.destroy()
