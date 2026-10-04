# Windows 部署安装器 · 关键记忆（v9 定型，2026-10-04）

## 是什么
Windows 实盘端一键安装器最终形态：**单文件 `install_v9.bat` = 一行 cmd 钥匙 + 全 Python 主体**（`python -x` polyglot，第1行cmd、第2行起Python）。已在 Windows（主机名"钧泽"）一次跑通。

## 铁律（未来改安装器必守）
1. **绝不用 cmd 写复杂逻辑**。cmd 只放第1行：`(py -3 -x "%~f0" || python -x "%~f0")` + 末尾 `pause`。其余 100% 用 Python。
2. Python 主体必须包顶层 `try/except`：traceback 上屏 + 写桌面 `quant-install-log.txt` + `notepad` 打开 + `input()` 等待。**绝不能让窗口闪退**。
3. 改完必须在 Mac 用 `python3 -x install_v9.bat --selftest` 真机验证（git/代理/ssh443认证），再交付；不要让用户当测试员。
4. 每次新版本用**新文件名**（install_v10.bat...），绕开浏览器 raw 缓存——v8 一直失败是因为用户双击的还是缓存的 v7。
5. 防双开锁：残留锁（手动关窗/闪退/重启）一律自动接管，绝不"8秒退出"。
6. 国内连 GitHub：SSH 走 `ssh.github.com:443` 首选（22常被封）→ SSH22 → HTTPS；自动探测本地代理 7890/7897/10809... 并配置 git 代理。

## 拓扑
- macOS：设计/开发/数据/调试；Windows：实盘运行。**绝不接任何券商真实账号/xtquant/QMT**；"实盘"= Windows 本机撮合引擎真实记账。
- 代码仓库：`you9095/quant-monitor`（master）；数据仓库（私有）：`you9095/quant-monitor-live-data`（master，唯一分支）。
- Windows 目录：代码 `D:\quant-monitor`；安装期数据通道 `D:\_qm_live`；日志 `D:\quant-monitor-install.log`。
- 三计划任务：QuantExecuteTask、QuantDecideTask、QuantBootCheck。

## 已知 P0 待改（10-07 前）
- **调度与开机时间不符**：电脑只在交易日 13:00–17:00 开机，但成交任务定在 09:35，永不触发。要改成"开机即跑当日 decide+成交"，用当日最新价/收盘价撮合，废弃 T+1 开盘价两段式。
- 10-06 17:00 跑 `reset_accounts.py` 归零（用户明确许可），10-07 从零实盘。

## 协作规则
- 用户说"开始盯"才挂监控；挂上后 **1 分钟无信号立即停**，不空等。
- 数据仓库是观察 Windows 的唯一远程通道；连不上 GitHub 前是物理盲区，此时靠脚本自动弹的桌面诊断。
