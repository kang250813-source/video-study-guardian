"""Windows 系统媒体会话（GlobalSystemMediaTransportControlsSessionManager）检测。

需要可选依赖 winsdk（pip install winsdk）。没有安装、或系统不支持时，自动退化为只依赖浏览器扩展计时。
作用与 Linux 版的 MPRIS 监听相同：有视频在播放时补充计时；锁定期间如果还有视频在播就暂停它。
"""
import asyncio
import threading
import time

try:  # 可选依赖
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    try:
        from winsdk.windows.media import MediaPlaybackType
    except Exception:  # pragma: no cover
        MediaPlaybackType = None
    AVAILABLE = True
except Exception:  # ImportError，或非 Windows
    SessionManager = PlaybackStatus = MediaPlaybackType = None
    AVAILABLE = False

# 会话来源程序名（AppUserModelID）里含有这些字样的视为视频播放器 / 浏览器
VIDEO_APPS = ("chrome", "msedge", "edge", "firefox", "brave", "opera", "vivaldi", "chromium",
              "vlc", "mpv", "potplayer", "mpc-hc", "mpc-be", "zunevideo", "wmplayer", "mediaplayer",
              "bilibili", "iqiyi", "youku", "qqlive", "tencentvideo", "mgtv", "kmplayer")


def looks_like_video(app_id, playback_type=None):
    """优先看系统给出的类型（视频/音乐）；没有类型信息时按程序名判断。"""
    if playback_type is not None and MediaPlaybackType is not None:
        try:
            if playback_type == MediaPlaybackType.VIDEO:
                return True
            if playback_type == MediaPlaybackType.MUSIC:
                return False
        except Exception:
            pass
    app = (app_id or "").lower()
    return any(name in app for name in VIDEO_APPS)


class MediaWatcher(threading.Thread):
    def __init__(self, guardian, interval=2.0):
        super().__init__(daemon=True, name="MediaWatcher")
        self.guardian = guardian
        self.interval = interval
        self.pause_requested = threading.Event()

    def request_pause(self):
        """锁定瞬间调用：尽快暂停正在播放的视频。"""
        self.pause_requested.set()

    def run(self):
        if not AVAILABLE:
            return
        try:
            asyncio.run(self._loop())
        except Exception:
            pass  # 媒体检测出错不影响守护本身

    async def _playing_sessions(self, manager):
        result = []
        for session in manager.get_sessions():
            try:
                info = session.get_playback_info()
                if info is None or info.playback_status != PlaybackStatus.PLAYING:
                    continue
                ptype = getattr(info, "playback_type", None)
                if looks_like_video(session.source_app_user_model_id, ptype):
                    result.append(session)
            except Exception:
                continue
        return result

    async def _loop(self):
        manager = await SessionManager.request_async()
        while True:
            try:
                playing = await self._playing_sessions(manager)
                g = self.guardian
                if playing and not g.work_mode:
                    if g.locked or self.pause_requested.is_set():
                        for s in playing:
                            try:
                                await s.try_pause_async()
                            except Exception:
                                pass
                    else:
                        g.activity()
            except Exception:
                pass
            self.pause_requested.clear()
            # 等待下一轮，但锁定请求到来时立即处理
            deadline = time.monotonic() + self.interval
            while time.monotonic() < deadline and not self.pause_requested.is_set():
                await asyncio.sleep(0.2)
