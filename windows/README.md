# 视频学习守护 · Windows 版

功能与 Ubuntu 版相同：孩子看网页或本地视频时累计时间，每满一轮（默认 10 分钟）就全屏锁住电脑，出一道当前年级的语文、数学或英语题。答对解锁并重新计时；答错再加一题；家长可以用管理员密码直接解锁。题库与 Ubuntu 版共用（仓库根目录的 `questions.py` 和 `bank/`）。

支持 Windows 10 / 11（64 位）。

## 下载

- **正式版本**：打开仓库的 **Releases** 页面，下载 `VideoStudyGuardian-windows.zip`。
- **最新构建**：打开仓库的 **Actions → Windows build**，点进最近一次成功的运行，在页面底部 **Artifacts** 下载 `VideoStudyGuardian-windows.zip`。（GitHub 会把 Artifact 再打包一层 zip，解压两次即可。）

把 zip 解压到一个固定位置，例如 `D:\VideoStudyGuardian\`（不要放在“下载”文件夹里随手删掉）。解压后的文件夹里有：

| 文件 | 用途 |
| --- | --- |
| `VideoStudyGuardian.exe` | 守护程序本体 |
| `家长控制面板.cmd` | 打开家长控制面板（需要管理员密码） |
| `重新设置.cmd` | 重新设置密码、年级（需要旧密码） |
| `浏览器视频监控扩展\` | Chrome / Edge 扩展 |
| `_internal\` | 程序运行所需文件和题库，请勿删除 |

> 程序没有数字签名，第一次运行时 Windows SmartScreen 可能提示“已保护你的电脑”，点击“更多信息 → 仍要运行”。

## 首次运行

1. **请在孩子使用的 Windows 账户里**双击 `VideoStudyGuardian.exe`。
2. 弹出“首次设置”窗口：输入两次管理员密码（至少 6 位）、每轮观看分钟数、孩子的年级和上册 / 下册。
3. 勾选“登录 Windows 时自动启动守护”（默认勾选），点击“保存”。守护随即在后台运行，不显示窗口。

密码以加盐哈希（PBKDF2-SHA256）保存在 `%APPDATA%\VideoStudyGuardian\config.json`，不保存明文。

## 安装浏览器扩展（Chrome / Edge）

扩展用来精确识别网页里的视频是否在播放，强烈建议安装。

1. Chrome 打开 `chrome://extensions`，Edge 打开 `edge://extensions`。
2. 打开“开发者模式”（Edge 在左下角）。
3. 点击“加载已解压的扩展程序”（Edge：“加载解压缩的扩展”），选择解压目录里的 `浏览器视频监控扩展` 文件夹。
4. 重新打开视频网页，右上角出现“学习守护：mm:ss”倒计时即表示在工作。

没有安装扩展时，程序也会（打包时成功装上可选组件 winsdk 的版本才有此功能）通过 Windows 系统媒体会话识别 Chrome、Edge、VLC、PotPlayer 等正在播放的视频，作为补充。

## 家长控制面板

双击 `家长控制面板.cmd`（或在守护运行时再次双击 `VideoStudyGuardian.exe`），输入管理员密码后可以：

- 设置每轮观看分钟数、年级（1–6）、上册 / 下册、科目、专题（全部 / 背古诗 / 背单词）、英语课本新版 / 旧版；
- 立即全屏锁定（测试用）；
- 开启 / 关闭工作模式（不计时、不锁屏，大人用电脑时打开）；
- 修改管理员密码；
- 启动 / 停止守护；
- 开启 / 关闭“登录 Windows 时自动启动”（只写当前用户的 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，不需要管理员权限）。

修改会自动生效，无需重启守护。

## 锁屏时

- 全屏窗口覆盖所有显示器并保持在最前面，忽略关闭和 Alt+F4。
- 锁定期间会拦截 Win 键、Alt+Tab、Alt+Esc、Ctrl+Esc、Ctrl+Shift+Esc 等切换窗口的快捷键，解锁后恢复。
- 锁定时会尽量暂停正在播放的视频；网页上也会显示遮罩。

## 局限（请务必了解）

这不是安全软件，懂电脑的孩子仍可能绕过：

- **Ctrl+Alt+Del 无法拦截**：这是 Windows 的安全组合键，任何普通程序都拦不住。孩子可以从那里打开任务管理器、注销或切换用户。
- **任务管理器**：可以结束 `VideoStudyGuardian.exe`；在“启动应用”里也能关闭它的自启动。
- 设置文件在孩子账户的 `%APPDATA%` 目录里，孩子账户本身可以修改或删除它（删除后下次启动会要求重新设置）。
- 系统媒体会话只能判断“正在播放”，有时无法区分视频和音乐。

**建议**：给孩子单独建一个 **Windows 标准用户（非管理员）账户**，在这个账户里运行守护；家长账户保留管理员权限并设好密码。必要时可配合 Windows 家庭安全（Microsoft Family Safety）禁用孩子账户的任务管理器。

## 从源码运行 / 自己打包

需要 Python 3.11 或更新版本（自带 tkinter）。

```bat
python windows\vsg_windows.py            :: 运行守护
python windows\vsg_windows.py --panel    :: 家长控制面板
python windows\vsg_windows.py --setup    :: 重新设置
python windows\vsg_windows.py --selftest :: 无界面自检

pip install -r windows\requirements.txt
python windows\build.py                  :: 生成 dist\VideoStudyGuardian-windows.zip
```

推送到 `main`（修改 `windows/`、`questions.py`、`bank/` 等）或手动运行工作流时，GitHub Actions 会自动打包；推送 `v*` 标签时会把 zip 附加到对应的 Release。

## 卸载

1. 在家长控制面板里关闭“自动启动”，点击“停止守护”。
2. 删除程序文件夹和 `%APPDATA%\VideoStudyGuardian`。
3. 在浏览器扩展页面移除“视频学习守护连接器”。
