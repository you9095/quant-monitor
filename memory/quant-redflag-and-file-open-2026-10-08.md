# 单文件记忆：跨日红灯锁定 + 双击打开（2026-10-08）

## 不可违背的铁律（用户明确）
- **17:00 后行情三源仍极端失败 → 红灯跨日持续，绝不自动补单。** 红灯第二天/周末/节假日一直亮；冻结一切自动成交；只有人工核对后运行解除脚本才恢复；**被冻结日不补单**。
- 国庆 10/1–10/7 休市、10/8 首日实际成交是正常逻辑，不是 bug，不再复核交易日历。
- 模拟盘与实盘收益口径各看各的，**不统一**（模拟=虚拟89天，实盘=本机真实撮合首日）。
- 一切数据永久标注性质；模拟盘、本机真实撮合，**绝不接任何券商真实账号/资金账号**。

## 红标机制（commit 287e45c）
- 持久标记：`live-data/_run_logs/trade_redflag.json`（独立于每日覆盖的 trade_health.json，经数据仓库 GitHub 同步 Mac）。
- 共享模块 `api/trade_redflag.py`：raise_redflag / load_redflag(仅未ack) / is_active / acknowledge。
- 三道闸门：①trade_supervisor 最前置（锁定日不判窗口/不成交/不补单，恒红，退出码2）；②run_daily_engine once/decide/execute/both 退出码3；③live_aggregator.build_trade_health 红标优先，当日 done/无心跳也强制恒红。
- 人工解除（唯一出口）：`python scripts/ack_trade_redflag.py`（或 trade_supervisor --ack-redflag），置 acknowledged 留痕+写 redflag_acknowledged 心跳+push 灭灯；状态查询 `--redflag-status`。
- 测试：tests/test_trade_redflag_lock.py 17 项；故障注入 11 项无回归。

## 双击打开（commit b21b5a5）
- file:// 双击 index.html 取不到数根因：不启后台 + 根相对 /api 解析成 file:///api + #44 删假数据回退 + 浏览器沙箱禁止网页起进程。
- 解法：head 注入 QM_IS_FILE/QM_ORIGIN，file:// 下 API 绝对指向 http://localhost:8000（后端 CORS ACAO:* 已放行）；data.js/data_v2.js/common.js/apiUrl 全部动态绝对化。
- 两个双击入口：后台在跑→双击 index.html；后台没跑→双击 `启动AI量化面板.command`(Mac,chmod+x) / `启动AI量化面板.bat`(Win,纯ASCII)。
- Mac 后端 launchd ai.quant.flask（RunAtLoad+KeepAlive，api/venv/bin/python，8000）；Windows run_simulation.py 经 start.bat/计划任务 step_restart_panel。

## 环境/验证备忘
- 隔离截图零污染范式：复制 live-data（删 .git）注入红标，`QM_LIVE_DATA_DIR=<tmp> PORT=8011 api/venv/bin/python api/real_data_server_v2.py`，截毕 lsof -ti tcp:8011 杀、删 tmp、确认真实 live-data 无 trade_redflag.json。
- 后端端口读 env `PORT`，数据目录读 env `QM_LIVE_DATA_DIR`。
- 截图目录：references/verify-2026-10-08-file-open/、references/verify-2026-10-08-redflag/。
