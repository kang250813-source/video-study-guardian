"""Windows 系统相关功能（ctypes / winreg）：单实例、开机自启、置前、屏幕尺寸、低级键盘钩子。

在非 Windows 系统上导入不会报错，所有函数退化为空操作，方便在 Linux 上做语法与逻辑测试。
"""
import os
import subprocess
import sys
import threading
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "VideoStudyGuardian"
MUTEX_NAME = "Local\\VideoStudyGuardian.Guardian"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.OpenMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.CallNextHookEx.restype = LRESULT
    user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
    user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)


# ───────────────────────── 单实例 ─────────────────────────
_mutex = None


def acquire_single_instance():
    """创建命名互斥量；已有守护在运行时返回 False。"""
    global _mutex
    if not IS_WINDOWS:
        return True
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return True  # 创建失败时不阻止运行，端口占用会作为第二道保护
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False
    _mutex = handle  # 进程存活期间一直持有
    return True


def guardian_running():
    """只检查互斥量是否存在，不占用它。"""
    if not IS_WINDOWS:
        return False
    handle = kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)  # SYNCHRONIZE
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return False


# ───────────────────────── 启动命令与自启动 ─────────────────────────
def guardian_command(*extra):
    """启动本程序的命令行：打包后是 exe，本身；源码运行时用 pythonw 运行 vsg_windows.py。"""
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra]
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    script = Path(__file__).resolve().with_name("vsg_windows.py")
    return [str(pyw if pyw.exists() else exe), str(script), *extra]


def _quote(cmd):
    return subprocess.list2cmdline(cmd)


def autostart_enabled():
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    """仅当前 Windows 用户（HKCU\\...\\Run），不需要管理员权限。"""
    if not IS_WINDOWS:
        return False
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _quote(guardian_command()))
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
    return autostart_enabled()


def launch_guardian():
    flags = 0
    if IS_WINDOWS:
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(guardian_command(), creationflags=flags, close_fds=True)


def stop_guardian(pid_file):
    """结束正在运行的守护进程（由已验证密码的家长面板调用）。"""
    try:
        pid = int(Path(pid_file).read_text().strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    try:
        if IS_WINDOWS:
            r = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                               creationflags=0x08000000)  # CREATE_NO_WINDOW
            return r.returncode == 0
        os.kill(pid, 15)
        return True
    except OSError:
        return False


# ───────────────────────── 窗口与屏幕 ─────────────────────────
def enable_dpi_awareness():
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 每显示器 DPI 感知
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen():
    """所有显示器拼起来的范围 (x, y, w, h)；非 Windows 返回 None。"""
    if not IS_WINDOWS:
        return None
    m = user32.GetSystemMetrics
    x, y, w, h = m(76), m(77), m(78), m(79)
    return (x, y, w, h) if w and h else None


def primary_screen():
    if not IS_WINDOWS:
        return None
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def force_foreground(hwnd):
    if not IS_WINDOWS or not hwnd:
        return
    try:
        if user32.GetForegroundWindow() != hwnd:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


# ───────────────────────── 低级键盘钩子 ─────────────────────────
VK_TAB, VK_ESCAPE, VK_F4 = 0x09, 0x1B, 0x73
VK_LWIN, VK_RWIN, VK_APPS = 0x5B, 0x5C, 0x5D
VK_CONTROL, VK_SHIFT = 0x11, 0x10
LLKHF_ALTDOWN = 0x20
WM_QUIT = 0x0012


def should_block(vk, alt, ctrl, shift=False):
    """锁定时要吞掉的组合键：Win 键、Alt+Tab、Alt+Esc、Ctrl+Esc、Alt+F4、Ctrl+Shift+Esc（尽力而为）。"""
    if vk in (VK_LWIN, VK_RWIN, VK_APPS):
        return True
    if alt and vk in (VK_TAB, VK_ESCAPE, VK_F4):
        return True
    if ctrl and vk == VK_ESCAPE:
        return True
    return False


class KeyBlocker:
    """锁屏期间安装 WH_KEYBOARD_LL 钩子，解锁后卸载。Ctrl+Alt+Del 由系统处理，任何程序都无法拦截。"""

    def __init__(self):
        self.thread = None
        self.thread_id = None
        self.hook = None
        self._proc = None
        self._ready = threading.Event()

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if not IS_WINDOWS or self.active:
            return
        self._ready.clear()
        self.thread = threading.Thread(target=self._run, name="KeyBlocker", daemon=True)
        self.thread.start()
        self._ready.wait(2)

    def stop(self):
        if self.active and self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            self.thread.join(2)
        self.thread = None

    def _callback(self, n_code, w_param, l_param):
        if n_code == 0:  # HC_ACTION
            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            alt = bool(kb.flags & LLKHF_ALTDOWN)
            ctrl = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
            if should_block(kb.vkCode, alt, ctrl):
                return 1
        return user32.CallNextHookEx(self.hook, n_code, w_param, l_param)

    def _run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        self._proc = HOOKPROC(self._callback)  # 保留引用，防止被回收
        self.hook = user32.SetWindowsHookExW(13, self._proc, kernel32.GetModuleHandleW(None), 0)  # WH_KEYBOARD_LL
        self._ready.set()
        if not self.hook:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(self.hook)
        self.hook = None
