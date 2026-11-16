#!/usr/bin/env bash
# 卸载：停止服务并删除服务文件和菜单图标（保留设置，如需一并删除请加 --purge）
set -uo pipefail
systemctl --user disable --now video-study-guardian.service 2>/dev/null
rm -f "$HOME/.config/systemd/user/video-study-guardian.service" "$HOME/.local/share/applications/video-study-guardian.desktop"
systemctl --user daemon-reload
[[ "${1:-}" == "--purge" ]] && rm -rf "$HOME/.config/video-study-guardian"
echo "已卸载。浏览器扩展请在扩展管理页手动移除。"
