# 单文件记忆：同源托管 + 单一启动器（2026-10-09 换方向）

## 决策
废弃"双击 index.html(file://) + 绿色按钮经 quant:// 自定义协议启动后台"路线（V1–V9/#49–#53 连修 8+ 版仍在 Windows 真机失败），改为：**Flask 后端同源托管整个前端 + 双击桌面一个图标静默起后台并自动开 http 面板**。提交 `f950a11`，已 push。

## 根因（不要再踩）
- file:// 页面 fetch localhost 触发 PNA/CORS，桌面 Chrome/Edge 真机拦截，headless 测不出。
- 网页经自定义协议启动本机程序会被拦截/闪烁/不回跳，注册表链路普通权限下脆弱。
- 结论：不与浏览器安全模型对抗；本机服务标准形态 = 本地 HTTP + 同源前端 + 桌面启动器。

## 关键事实
- 后端 `api/real_data_server_v2.py`：
  - 静态托管白名单 `_FRONT_PAGES`（6 个 html）+ assets 白名单扩展名 + favicon；`_FORBIDDEN_PREFIX`（api/scripts/live-data/.git/venv/strategies/signals/data/config/memory/work_logs/knowledge 等）与 `..` 一律 404。catch-all 曾把源码、账本、.git/config 全暴露（已堵）。
  - 模拟盘组合总览新函数 `build_simulator_portfolio_summary()`（与 overview 非 live 同口径，信号 live_total_pnl/live_total_return，仅 live_days>0）；修复顶部 KPI 与卡片金额恒 0。
- 启动器 `scripts/launch_panel.py --open`：幂等 + wait_healthy + open_in_browser（http://localhost:8000/）；守护任务不带 --open 不弹浏览器。
- 根目录 `AI量化面板.vbs`（纯 ASCII/CRLF，pythonw 无窗 launch_panel --open）；`win_self_register._create_desktop_shortcut()` 用 PowerShell EncodedCommand(UTF-16LE base64) 建桌面"AI量化面板.lnk"；update-and-start.bat、Mac .command 统一 --open。
- index.html：遮罩删 quant://，绿色按钮 gotoPanel() 顶层跳 http；toggleDataMode 用 URLSearchParams 同步 data_mode 再导航（修带参切换无效）。
- 数据口径：模拟盘合计 60000→88383.16（+47.31%）；实盘模拟首日 59940.30（-59.70/-0.10%，4 买入 2 空仓，账本 3b809f2）。
- Mac launchd ai.quant.flask：ProcessType=Standard；偶发 -9 是助手 kickstart -k / 后台任务清理进程组所致，非崩溃。
- Windows 更新：下次开机计划任务自动 git reset 拉新；或双击 update-and-start.bat 一次，之后只用桌面"AI量化面板"图标。

## 铁律延续
- bat/vbs 纯 ASCII + CRLF；中文走 PowerShell EncodedCommand。
- 模拟/实盘/回测/UI虚拟四套口径分离，金额必标性质，模拟盘子页面诚实空态。
- 静态文件对外必须白名单；真机桌面浏览器验证为准，headless 不算。
- git add 排除 data/v24_*.csv、ratchet_final_baseline、ratchet_report_*.md、live-data、logs/launch_panel.lock。
