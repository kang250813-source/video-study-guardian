#!/usr/bin/env bash
# 视频学习守护 一键安装（Ubuntu / Debian 桌面，GNOME 或其他支持 XWayland 的桌面）
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/usr/bin/python3

# 依赖：系统自带 Python 的 GTK3 绑定
if ! $PY -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk' 2>/dev/null; then
  echo "需要安装 GTK3 的 Python 组件（会要求输入本机密码）："
  sudo apt-get install -y python3-gi gir1.2-gtk-3.0
fi

if [[ ! -f "$HOME/.config/video-study-guardian/config.json" ]]; then
  $PY "$DIR/guardian.py" --setup
fi

mkdir -p "$HOME/.config/systemd/user" "$HOME/.local/share/applications"
cat > "$HOME/.config/systemd/user/video-study-guardian.service" <<UNIT
[Unit]
Description=视频学习守护（本机全屏答题锁）
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$PY $DIR/guardian.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT

cat > "$HOME/.local/share/applications/video-study-guardian.desktop" <<DESK
[Desktop Entry]
Version=1.0
Type=Application
Name=视频学习守护
Comment=家长控制、全屏答题锁与观看时长设置
Exec=$PY $DIR/control.py
Icon=security-high
Terminal=false
Categories=Utility;Education;
DESK

systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS || true
systemctl --user daemon-reload
systemctl --user enable --now video-study-guardian.service
echo
echo "已启动。在应用菜单里搜索“视频学习守护”打开家长控制面板。"
echo "接下来在 Chrome 加载扩展：$DIR/浏览器视频监控扩展"
