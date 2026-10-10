# 单文件记忆 · 成交周期守护与事后补记（2026-10-10）

> 数据性质铁律：全程**模拟盘 + Windows 本机真实撮合，绝不连接任何券商真实账号/资金账号**。
> 对账单/成交/盈亏是本机按真实行情撮合的真实结果，非回测、非写死。一切数据永久标注性质。

## ★最高优先：成交规则（2026-10-10 用户亲自更正，覆盖旧档）

1. **唯一禁止自动成交/补单的条件 = 东财→腾讯→新浪三源真实价全部失败、拿不到真实价。**
2. 拿得到当日真实价（盘中实时价 / 收盘后当日收盘价）就必须成交。A股15:00收盘后现价=收盘价，下午/傍晚都能补当日。
3. 失败按约10分钟持续重试（前几轮2/3/5分钟退避，之后固定10分钟），循环到成功，**绝不用旧价、绝不伪造、绝不直接判当日不成交**。
4. 跨日漏单：取得到漏单日真实收盘价（历史日K）就**自动事后补记并标"事后补记"**；连历史真实价都三源全失败（几乎不可能）才亮红灯常亮等人工。
5. **不存在"17点后不补单"规则**——那是把一次"先不补"误固化，已更正（旧档保留）。

## 调度架构（2026-10-10 起，取代长驻监督器）

- 核心是 `trade_supervisor.py --guard`（`guard_once`）幂等周期守护，被计划任务每10分钟唤醒：
  红标→秒退；跨日补记上线后缺口；非交易日→秒退；上午<13点→秒退；已成交→秒退；
  交易日13点后未成交→取真实价成交，三源失败写 retrying 心跳、下次再来，不锁死。
- Windows 任务 **QuantTradeGuard**（XML，`win_self_register._register_trade_guard_task`）：
  登录后2分钟起PT10M(持续1天) + 工作日13:00起PT10M(持续10H)；
  StartWhenAvailable=true、电池不阻止、RestartOnFailure、IgnoreNew、单次15分钟上限。
  **后端启动自动 self_register，Windows 开机拉后端即自动注册，无需手动跑安装器。**
- daily_task 交易步骤也改调 `--guard`；旧 onlogon/13:05/15:10 保留为额外幂等唤醒。
- 每天首次 guard 必 push `guard_triggered` 心跳（解决"Mac 分不清没触发还是崩"）。

## 事后补记工具链

- `run_daily_engine.load_hist_klines(code,end_date,n)`：缓存→akshare东财qfq→新浪日K→腾讯日K，
  最后一根日期必须==补记日；仅用于补记/信号复盘，禁用于盘中实时。
- `scripts/backfill_day.py --date YYYY-MM-DD[,…] --yes [--no-push] [--reason]`：交易日/连续性/幂等校验。
- `scripts/sync_live_data.py push --force [note]`：补记/运维心跳跳过13-17窗口。
- 补记记录字段：`data_nature="实盘模拟(事后补记,<date>真实收盘价,本机撮合,非回测,不接券商)"`、`backfill=true`、`backfill_for_date/backfill_run_at`。
- 聚合层 live_aggregator 把 backfill 透传到每笔成交与每日曲线点；trades/pnl_history 显示橙色"事后补记"徽章（.badge-backfill）。

## 已钉死的坑

- 新浪/腾讯历史K URL：市场前缀(sz/sh)只拼一次，拼两次变 `sz159981159981` 会全空。
- 新浪日K极易限流：串行、间隔≥1.2–2s、禁并发；symbol 只拼一次前缀；必须 Referer finance.sina.com.cn、trust_env=False 直连。
- 跨日补记只补"首个已成交日之后、今天之前"的连续缺口，**绝不补系统上线(归零 2026-10-06、首日 2026-10-08)之前的历史日期**；乱序拒绝(rc=3)不亮红灯，只有真实价三源全失败(rc=4/5)才亮。
- 非交易日绝不能跑引擎（曾在 Mac 周六上午误跑生成 daily/2026-10-10 脏数据，已回滚）。
- bat/vbs 必须纯 ASCII+CRLF（中文用 PowerShell EncodedCommand UTF-16LE）；Python/HTML 内中文正常。

## 仓库与验证锚点

- 代码 `git@github.com:you9095/quant-monitor.git` master：守护 912be77、补记UI d2d58db。
- 数据 `git@github.com:you9095/quant-monitor-live-data.git` master：补记后 751392a（daily=10-08、10-09）。
- 10-09 补记后六策略总权益 60015.18（首日10-08 59940.30 −59.70；次日 +74.88）。
- 测试：tests/test_trade_guard.py、test_trade_supervisor_fault_injection.py、test_trade_redflag_lock.py 全绿。
- Mac 面板实盘入口 http://127.0.0.1:8000/?data_mode=live（参数名是 data_mode，不是 mode）。
- Windows 远程自检：读数据仓库 `_deploy_status/钧泽.json`(code_commit) 与 `_run_logs/trade_health.json`，不让用户截图。
