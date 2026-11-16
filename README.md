# 视频学习守护（Video Study Guardian）

给孩子用的 Ubuntu 桌面小工具：网页或本地视频播放时累计观看时间，每满一轮（默认 10 分钟），就全屏锁住电脑，出一道当前年级的语文、数学或英语题。答对解锁并重新计时；答错再加一题；家长可用管理员密码直接解锁。

## 功能

- 按 **年级（1–6）** 和 **上册 / 下册** 出题，题目按 2024/2026 新教材单元编写（统编语文、人教数学、人教 PEP 英语）。
- **专题模式**：全部 / 背古诗 / 背单词。
- 家长控制面板：设置每轮分钟数、年级、上下册、科目、专题、英语教材版本，暂停守护，工作模式。
- 同时支持浏览器扩展（精确识别网页视频）和 Linux 媒体会话（MPRIS，识别 VLC、MPV 等播放器）。
- 服务只监听 `127.0.0.1:8167`，不对外开放；不联网、不收集数据。

## 安装

```bash
git clone https://github.com/kang250813-source/video-study-guardian.git
cd video-study-guardian
bash install.sh
```

首次安装会询问管理员密码、每轮分钟数、孩子的年级和上下册。密码以加盐哈希保存在 `~/.config/video-study-guardian/config.json`，不会进入仓库。

然后在 Chrome 打开 `chrome://extensions`，开启“开发者模式”，点击“加载已解压的扩展程序”，选择仓库里的 `浏览器视频监控扩展` 文件夹。重新打开视频网页，右上角出现倒计时即表示在工作。

在应用菜单搜索“视频学习守护”可打开家长控制面板。卸载：`bash uninstall.sh`。

## 其他浏览器

- **Edge、Brave、Chromium、Vivaldi**：在各自扩展管理页开启开发者模式，加载同一个扩展文件夹。
- **Firefox**：打开 `about:debugging#/runtime/this-firefox`，“临时载入附加组件”，选择扩展里的 `manifest.json`（重启后需重新载入）。

## 题库

题库在 `bank/<科目>/g<年级><a=上册|b=下册>.json`，格式见 `questions.py` 顶部说明；每个科目目录下的 `SOURCES.md` 写明了教材版本和来源。部分下册新教材尚未出版，相应题库标为“待更新”，欢迎提交 PR 修正或补充。

## 说明

- 全屏窗口会拦截 Esc、Alt+F4 等常见退出操作，但它不是安全软件，懂电脑的孩子仍可能绕过；建议配合独立的孩子账户使用。
- 系统媒体会话只能判断“正在播放”，无法区分视频和纯音频。

## Windows 版

`windows/` 目录里是 Windows 10/11 版本（Python + tkinter，与本版共用题库和浏览器扩展），可在仓库的 **Releases** 或 **Actions → Windows build** 下载打包好的 `VideoStudyGuardian-windows.zip`，解压后双击 `VideoStudyGuardian.exe` 完成首次设置。详细说明见 [windows/README.md](windows/README.md)。

## Android 版

`android/` 目录是手机版（Android 8.0+）：孩子在抖音、快手、B站等视频 App 里累计观看满设定分钟数后，全屏答题界面会盖住所有应用，答对解锁、答错加题，家长密码可直接解锁；与电脑版共用 `bank/` 题库。

- 下载：Releases 里的 `VideoStudyGuardian.apk`，或 Actions → **Android APK** 的构建产物（推送 `v*` 标签会自动发布）。
- 安装、权限设置、OPPO/ColorOS 自启动与后台运行设置、使用限制，见 [android/README.md](android/README.md)。

## 许可

MIT
