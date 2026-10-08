# 单文件记忆：一个文件一键启动后台（2026-10-08，commit 6587173）

## 用户铁律
- 只接受"打开 index.html 一个文件解决所有问题"；后台没开也要在**页面里点按钮**启动，拒绝再双击第二个文件。
- 以后禁止缩略词：git pull 必须写"git pull（拉取最新代码）"并给完整步骤。

## 浏览器硬边界
- 网页 JS 无法直接启动本机程序（沙箱）；合规桥接=自定义协议 quant://（一次性注册）+ 后台开机自启/自愈。
- 系统级注册（计划任务/注册表/LaunchServices）不能靠 git pull 完成，必须一次提权运行安装器；之后永久生效。

## Windows
- scripts/panel_guard.vbs（wscript 静默、幂等、检8000）+ scripts/start_panel_quiet.bat（纯ASCII，start /min venv python run_simulation.py）。
- setup.py：QuantPanelGuard 任务（onlogon 30s + 每5分钟重复 P3650D、HighestAvailable、IgnoreNew，XML /create）；注册表 HKCU\Software\Classes\quant 绑定 `wscript.exe "...panel_guard.vbs" "%1"`。
- 生效：管理员重跑一次 install_v9.bat（幂等）；脚本本体以后随每日拉取更新。

## macOS
- scripts/QuantLauncher.app（Info.plist CFBundleURLSchemes=quant、LSUIElement；MacOS/QuantLauncher 立即 exit，启动逻辑 nohup bash -c detach：kickstart ai.quant.flask → 3s → venv 兜底）。
- scripts/register_quant_protocol_mac.sh 一次性 lsregister（本机已注册）。launchd ai.quant.flask 已常驻。
- 关键坑：handler 不能同步等待启动，否则 `open quant://` 挂起；必须立即返回 + 后台 detach。

## 前端
- 遮罩 #conn-error-overlay 绿色主按钮 launchBackend()：location.href='quant://start-backend' + 每2s轮询 /api/v1/strategies?data_mode=live，r.ok 即 reload，最多45次；.ce-btn-primary 样式；双击启动文件降级为备用。

## 验证
- setup.py py_compile OK；守护 XML ElementTree 良构；vbs/bat 字节级纯 ASCII。
- Mac 实测：bootout 停服→open -g quant://→8s 拉起 health200→trap 恢复 launchd（PID 76759）。
- 截图 references/verify-2026-10-08-one-click/overlay_start_button.png。
