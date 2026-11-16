"""视频学习守护 Windows 版：与界面无关的核心逻辑（配置、密码、出题、计时、本机 HTTP 接口）。

这个模块不导入任何 Windows 专用库，也不导入 tkinter，可以在 Linux 上做无界面测试。
题库直接复用仓库根目录的 questions.py 和 bank/；打包成 exe 后两者被放进程序目录。
"""
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import sys
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "VideoStudyGuardian"
APP_TITLE = "视频学习守护"
FROZEN = bool(getattr(sys, "frozen", False))
HOST, PORT = "127.0.0.1", int(os.environ.get("VSG_PORT", "8167"))
WRONG_WAIT = 3  # 答错后需等待的秒数，防止乱点
PBKDF2_ROUNDS = 210_000  # 与 Linux 版相同，配置文件格式互通


def resource_root():
    """questions.py 与 bank/ 所在目录：源码运行时是仓库根目录，打包后是 PyInstaller 的资源目录。"""
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


ROOT = resource_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import questions  # noqa: E402  (仓库根目录的 questions.py)

questions.BANK_DIR = ROOT / "bank"  # 打包后 __file__ 不可靠，显式指定题库位置


def app_dir():
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


CONFIG_FILE = Path(os.environ["VSG_CONFIG"]) if os.environ.get("VSG_CONFIG") else app_dir() / "config.json"
PID_FILE = CONFIG_FILE.parent / "guardian.pid"


# ───────────────────────── 文本与密码 ─────────────────────────
def normalize(value):
    """比较填空答案：忽略空格、大小写、全角/半角、弯引号（与 Linux 版一致）。"""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    for a, b in (("’", "'"), ("‘", "'"), ("…", "."), ("：", ":")):
        text = text.replace(a, b)
    return re.sub(r"\s+", "", text)


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def check_password(config, password):
    try:
        _, candidate = hash_password(password or "", bytes.fromhex(config["salt"]))
        return hmac.compare_digest(candidate, config["password_hash"])
    except (KeyError, TypeError, ValueError):
        return False


# ───────────────────────── 配置 ─────────────────────────
def default_term(month=None):
    month = month or time.localtime().tm_mon
    return "上" if month >= 8 or month == 1 else "下"


def validate_setup(password, password2, minutes, grade, term):
    """首次设置的输入检查；返回错误提示，没有问题时返回 None。"""
    if len(password or "") < 6:
        return "密码至少需要 6 位。"
    if password != password2:
        return "两次密码不一致。"
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return "分钟数必须是 1 到 60 的整数。"
    if not 1 <= m <= 60:
        return "分钟数必须是 1 到 60 的整数。"
    if str(grade) not in {"1", "2", "3", "4", "5", "6"}:
        return "年级必须是 1 到 6。"
    if term not in {"上", "下"}:
        return "请选择“上”或“下”册。"
    return None


def new_config(password, minutes=10, grade=6, term=None):
    salt, digest = hash_password(password)
    return {"salt": salt, "password_hash": digest, "minutes": max(1, min(60, int(minutes))),
            "grade": int(grade), "term": term or default_term(), "mode": "全部",
            "subjects": ["语文", "数学", "英语"], "english_edition": "new", "work_mode": False}


def load_config(path=None):
    path = Path(path or CONFIG_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "salt" not in data or "password_hash" not in data:
        return None
    data.setdefault("minutes", 10)
    return data


def save_config(data, path=None):
    """先写临时文件再替换，避免守护读到写了一半的配置。"""
    path = Path(path or CONFIG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# ───────────────────────── 出题 ─────────────────────────
FALLBACK_QUESTION = ("fill", "数学", "题库是空的，请家长检查 bank 文件夹。临时题：3 + 4 = ?", ["7"])


def pick_question(config, recent=(), rng=random):
    """与 Linux 版相同：questions.pool(config) → 先随机选科目，再在该科目里选题；选择题打乱选项。"""
    allq = [questions.to_tuple(x) for x in questions.pool(config)] or [FALLBACK_QUESTION]
    pool = [q for q in allq if q[2] not in recent] or allq
    subject = rng.choice(sorted({x[1] for x in pool}))
    q = rng.choice([x for x in pool if x[1] == subject])
    if q[0] == "choice":
        _, subject, prompt, opts, right = q
        order = list(range(len(opts)))
        rng.shuffle(order)
        return ("choice", subject, prompt, [opts[i] for i in order], order.index(right))
    return q


class QuizSession:
    """一次锁屏里的答题状态：答对 need-1，答错 need+1，need 归零即解锁。"""

    def __init__(self, config_getter, rng=random):
        self.config_getter = config_getter
        self.rng = rng
        self.recent = []
        self.question = None
        self.need = 1

    def start(self):
        self.need = 1
        return self.next()

    def next(self):
        self.question = pick_question(self.config_getter(), self.recent, self.rng)
        self.recent = (self.recent + [self.question[2]])[-30:]
        return self.question

    def answer_choice(self, index):
        """返回 (是否答对, 正确选项序号)。"""
        right = self.question[4]
        ok = index == right
        self.need += -1 if ok else 1
        return ok, right

    def answer_fill(self, text):
        """返回 (是否答对, 标准答案)。"""
        ok = normalize(text) in {normalize(v) for v in self.question[3]}
        self.need += -1 if ok else 1
        return ok, self.question[3][0]

    @property
    def done(self):
        return self.need <= 0


# ───────────────────────── 计时 ─────────────────────────
class Guardian:
    """与 Linux 版 Guardian 行为一致：最近 7 秒内有视频心跳才计时；配置文件变化自动生效。"""

    def __init__(self, config, config_path=None, on_lock=None):
        self.config_path = Path(config_path or CONFIG_FILE)
        self.config = config
        self.round_seconds = config["minutes"] * 60
        self.remaining = float(self.round_seconds)
        self.last_activity = 0.0
        self.last_tick = time.monotonic()
        self.locked = False
        self.lock = threading.Lock()
        self.on_lock = on_lock or (lambda: None)
        self.config_mtime = self._mtime()

    @property
    def work_mode(self):
        return bool(self.config.get("work_mode"))

    def _mtime(self):
        try:
            return self.config_path.stat().st_mtime
        except OSError:
            return 0

    def reload_config(self):
        mtime = self._mtime()
        if mtime == self.config_mtime:
            return
        self.config_mtime = mtime
        new = load_config(self.config_path)
        if not new:
            return
        with self.lock:
            minutes_changed = new.get("minutes") != self.config.get("minutes")
            self.config = new
            self.round_seconds = new["minutes"] * 60
            if minutes_changed:
                self.remaining = float(self.round_seconds)
            unlock = self.work_mode and self.locked
        if unlock:
            self.unlock()

    def snapshot(self):
        return {"remaining": int(round(self.remaining)), "locked": self.locked,
                "minutes": self.config["minutes"], "work_mode": self.work_mode}

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
            threading.Thread(target=self.on_lock, daemon=True).start()
        return newly_locked

    def force_lock(self):
        if self.work_mode:
            return self.status()
        with self.lock:
            if not self.locked:
                self.remaining = 0.0
                self.locked = True
        threading.Thread(target=self.on_lock, daemon=True).start()
        return self.status()

    def unlock(self):
        with self.lock:
            self.locked = False
            self.remaining = float(self.round_seconds)
            self.last_activity = 0.0


# ───────────────────────── 本机 HTTP 接口（与 guardian.py 相同） ─────────────────────────
class Handler(BaseHTTPRequestHandler):
    """GET /status；POST /activity；POST /lock；OPTIONS 预检。CORS 与 Linux 版一致。"""
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
        self.end_headers()
        self.wfile.write(body)

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


def make_server(guardian, host=HOST, port=PORT):
    handler = type("BoundHandler", (Handler,), {"guardian": guardian})
    return ThreadingHTTPServer((host, port), handler)


def request(path, method="GET", port=PORT, timeout=2):
    """访问本机守护接口；绕过系统 / 环境代理（Windows 上 urllib 会读取 IE 代理设置）。"""
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(f"http://{HOST}:{port}{path}", method=method)
    with opener.open(req, timeout=timeout) as result:
        return json.loads(result.read())
