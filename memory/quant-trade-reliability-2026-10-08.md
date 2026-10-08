# 量化监控项目 · 成交可靠性闭环关键记忆（2026-10-08，#43/#44）

> 配套阅读：memory/quant-live-architecture-2026-10-06.md（系统总览）。本篇是"当日成交如何保证真实、可见、可自愈"的速查，改动成交链路前先读。

## 一、最高约束（不可动摇）
- 模拟盘、本机真实撮合，**绝不连接任何券商真实账号/资金账号/xtquant/QMT**。
- 成交**必须用当日真实价**：东财→腾讯→新浪三源，缺任一必需标的（目标∪持仓）的真实价就**不撮合、不动账**。**禁止历史日线收盘价兜底（close_fallback）**，禁止旧价/快照/前向填充。
- 用户明确决策：三源全失败**必须持续重试直到成功**（先快后稳：2/3/5 分钟，之后固定 10 分钟无限循环），**绝不接受"全失败即当日不成交亮红灯终止"**。仅 17:00 窗口末仍极端失败才挂 pending_overnight 红灯。

## 二、成交链路新架构（commit d9d9305）
- `run_daily_engine.py`
  - `fetch_realtime_quotes(pool, spot_em_df=None)` → `(prices, source, detail, per_source)`，source ∈ realtime/partial/none；三源：东财 ak.fund_etf_spot_em（_ak_spot_em_no_proxy 禁代理直连，push2delay 偶发 502）、腾讯 qt.gtimg.cn（gbk, Referer gu.qq.com）、新浪 hq.sinajs.cn（gbk, Referer finance.sina.com.cn）。
  - `run_once` 返回结构化 dict：status ∈ already/traded/idle/no_history/missing_price/error；missing_price 在 broker.save 之前返回；idle=空仓无目标也落盘 price_source=idle。
  - `run_once_all` 单轮汇总，每轮只预取一次东财快照。
- `trade_supervisor.py`（新增，常驻）：窗口 13:00–17:00；BACKOFF=[120,180,300] 后 STEADY_INTERVAL=600；LOCK_STALE_SECONDS=840；WRAP_UP_MINUTES=4（约16:56 停）；15:00 后取当日真实收盘价（盘后接口现价=收盘）；非交易日 no_trade_day 退出；参数 --date/--no-push/--max-minutes。
  - 心跳 `live-data/_run_logs/trade_health.json`：date/status(running 时写 retrying/done/pending_overnight/no_trade_day/outside_window)/attempt/price_sources{em,tencent,sina}/strategies{sid:{status,missing,required,target,trades,price_source,detail,total_asset,today_pnl,error}}/done_count/total/trades_total/pending_strategies/retry_reasons/next_retry_at/backoff_seconds/note。
  - 锁 `_run_logs/supervisor.lock`（按心跳时间戳判活，陈旧锁接管），日志 `_run_logs/<date>_supervisor.log`。

## 三、Windows 四计划任务（setup.py 注册，均 /rl HIGHEST）
- QuantDailyTrade：onlogon +3min → daily_task.py trade（主）。
- **QuantDailyNoon：工作日 13:05 → trade（纯时间触发双保险，治睡眠解锁/未重登导致 onlogon 不触发；10-08 事故根因）**。
- QuantDailyTradePM：工作日 15:10 → trade（收盘兜底，盘后真实收盘价，当日幂等）。
- QuantBootCheck：onlogon +1min → scripts/fix_and_report.py（只自愈+上报，不交易）。
- daily_task trade 顺序：更新代码(git reset --hard origin/master)→装依赖→**监督器(timeout 16500)**→兜底 push→部署心跳→重启面板。
- **注意：git pull 不重建计划任务；改 setup.py 任务后必须在 Windows 重跑安装器/注册段才生效。**

## 四、面板健康灯（Mac 端）
- api/live_aggregator.py `build_trade_health()` 读心跳，无文件返回 available:false/no_heartbeat（不臆造）。
- real_data_server_v2.py overview live 注入 `trade_health`；data.js 透传；index.html 实盘横幅：done 绿（✅N/6、M笔、价源、轮次）、retrying 黄（🟠第N轮、缺哪些、下次hh:mm、绝不用旧价）、pending_overnight 红。
- Mac 后端 LIVE_SYNC：启动 pull 一次 + 每 180s ff-only 自动 pull 数据仓库；正确入口 http://localhost:8000/?data_mode=live|simulator，禁止双击 file:// index.html（会显示未连接遮罩，不再有假数字）。

## 五、测试与定位
- 故障注入：tests/test_trade_supervisor_fault_injection.py（临时账本 + monkeypatch，11 断言）。
- 三源冒烟事实：东财节点可能整段 502（与本机代理无关），腾讯/新浪独立可用 → 单源挂不影响成交，只有三源齐失才重试。
- 撮合费用：佣金率 0.00025 最低 5、印花税 0.0005（仅卖）、滑点 0.001（买价×1.001）、100 股整手、T+1、加权平均成本。

## 六、未决边界
- 17:00 后极端失败的**跨日自动补单未实现**（红灯+次日处理），是否自动按昨日收盘价补待用户拍板（涉隔日资金口径）。
- is_trading_day 长假准确性需复核；模拟盘"总盈亏/模拟总收益"两套口径历史遗留待统一。
