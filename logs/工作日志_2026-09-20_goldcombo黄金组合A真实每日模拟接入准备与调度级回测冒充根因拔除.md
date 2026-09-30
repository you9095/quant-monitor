# 工作日志 · 2026-09-20 · 黄金组合A（goldcombo）真实每日模拟接入准备 + 调度级回测冒充根因拔除

## 一、任务背景（用户最高优先级 KPI）
- 用户指令：黄金组合A（goldcombo，下文每次出现中文"黄金组合A策略"）认可"无真实数据就空着"，要求**自周一 2026-09-21 起接入真实每日信号**，今天（9/20 周日休市）先做好全部提前准备。
- 不可妥协的核心 KPI：**基于真实行情的模拟交易**；快照/假设/前向填充/回测冒充实盘/折中一律禁止。
- 今天数据只到最近交易日 2026-09-18（周五），9/21 周一是实盘模拟首日。

## 二、调研结论：黄金组合A此前根本没有"逐日真实模拟引擎"
| 既有文件 | 真实身份 | 问题 |
|---|---|---|
| `strategies/goldcombo/goldcombo_ratchet_ashare.py` | **棘轮参数迭代器**（R0→R50，全 A 股池，2Y/5Y 固定窗口，约 1.5h） | 不是每日账户模拟，数据窗口写死 2024-08-13~2026-08-13 |
| `scripts/run_goldcombo_backtest.py` | backtrader 壳，数据是**随机 stub**，已被 `raise SystemExit` 双保险封死 | 从未接真实数据跑通 |
| `scripts/regenerate_goldcombo_signal.py` | 只读棘轮 baseline 生成**静态占位** signal（positions=[]、live_days=0） | 不是每日信号 |
| `/Users/junze/goldcombo_real_backtest/v24/T4_5y/run_backtest_5y_v24.py` + `strategies/goldcombo/goldcombo_strategy_ashare_v24.py` 的 **DMAStrategy** | **真正的策略引擎**（raw_output.log 证明 8/17 真实跑通：13 标的、2.85 秒、5 万本金、+4.4311%、21 笔、DD 8.24%） | 此前没有"每日切片"版本 |

V24 策略逻辑：DMA(10/50) 上穿 AMA(10) 金叉买入、下穿死叉卖出；过滤=成交量>20 日均量×1.5 + RSI 30~70；市场过滤=沪深300(510300) 收盘在 MA200 之上否则清仓不开新；10% 硬止损 + 15% 移动止盈 + 10 天冷却；最多持 5 只、单只 20%；CB 10 张/手、ETF/STK 100 股/手。**信号极稀疏（5 年 21 笔）**。

## 三、★调度级"回测冒充实盘"根因拔除（本轮最关键发现）
`scripts/daily_catchup_runner.sh` 旧第 5 步：
```bash
nohup "$PYTHON" goldcombo_ratchet_ashare.py --output-path "$WORK_LOGS/goldcombo/goldcombo_${TODAY}.json" &
```
**每个交易日盘后把棘轮回测日志（2.58MB、version 3.0_ashare、50 rounds）直接写进 `~/.hermes/work_logs/goldcombo/`**——这正是 9/17、9/18、9/20 三个 2.58MB 大文件的来源，也是黄金组合A长期"看起来有 work_log、实则是棘轮回测"的调度级根源（违反 PROJECT_RULES 规则7：回测/实盘物理隔离）。

处置：
1. 三个误置大文件**移动归档**到 `strategies/goldcombo/ratchet_archive/misplaced_worklogs/`（不删除、可追溯），work_logs/goldcombo 清空。
2. catchup 第 5 步整段删除，替换为黄金组合A真实每日模拟链路；棘轮回测不再挂每日调度（低频参数迭代，输出只许留在 strategies/goldcombo/）。

## 四、新建/改造产物（全部验证）
1. **`scripts/fetch_v24_pool_kline.py`（新建，已 --full 跑通）**：新浪真实日线，禁代理；`--full`=1300 根，默认增量 120 根去重 append；退市不补点。写入 `data/v24_etf_kline`(5)、`v24_stk_kline`(3)、`v24_bonds`(5)。
   - 13 标的：ETF 510300/510500/512880/512690/512480；STK 000001/600519/000333；CB 113050/110079/113011/113013/113016。
   - **5 只转债已全部退市**（新浪真实）：113011 止 2023-03-13、113013 止 2023-07-03、113016 止 2023-06-16、113050 止 2025-07-14、110079 止 2025-07-01。2026 实盘真实可交易=5 ETF+3 STK 共 8 个；退市数据如实止于最后交易日，不换券（换券属策略迭代，需用户另行决定）。
2. **`scripts/goldcombo_daily_run.py`（新建，dry-run 验证通过）**：黄金组合A唯一每日真实模拟入口。venv+backtrader，**复用 DMAStrategy 不改一字**；`LiveDMAStrategy` 加实盘起点门控（live_start 前只 warm-up 指标、账户一笔不交易）+ 成交记录 + 逐日净值；`set_coc(True)` 当日收盘价成交；5 万本金；写标准 JSONL（morning/afternoon 两行，daily_pnl{total,per_etf,cumulative,return_pct,trade_count}、positions_before/after、trade.securities、capital、return_unit='percent'、live_start_date）。
3. **`scripts/rebuild_signals_from_worklogs.py`（改造）**：删除黄金组合A回测特殊分支与 `--keep-goldcombo`；6 策略同构走"逐日 work_logs→signals"，本金 per-sid（5 个 ETF 各 1 万、黄金组合A 5 万）；无 work_log 不生成 signal（留空）；输出 `return_unit='percent'`、透传 live_start_date；ACTION_MAP 补 FLAT/买入/卖出；session 判定改 endswith 兼容。
4. **`api/real_data_server_v2.py`（改造）**：组合汇总硬编码 `active_count*10000` 改为按各在跑策略真实本金求和 `active_init`（支持黄金组合A 5 万）；收益率信任 signal 显式 `return_unit`。
5. **`api/live_data.py`（改造）**：portfolio_summary 同样信任 `return_unit='percent'`（曲线/组合本就动态读 config 本金，无需另改）。
6. **`config/strategies.json`（改造）**：黄金组合A initial_capital 1万→**5万**（策略 setcash 锁死）；修正过时 pool 描述为 V24 真实 13 标的；class_name 改回 DMAStrategy；data_period 改"实盘起点 2026-09-21"；补 daily_runner 路径。
7. **`scripts/daily_catchup_runner.sh`（改造）**：新增第 4 步黄金组合A（系统 python 增量更 V24 K线 → venv 跑 goldcombo_daily_run 逐日幂等补跑，实盘起点 2026-09-21 前一律跳过、K线未到当日则等下次不造假），第 5 步统一 rebuild 6 策略；删除棘轮回测调度。

## 五、过程中修掉的两个真实 bug
- **坑：收益率单位"启发式猜测"**。`_normalize_return_pct` 用"绝对值<1 且≠0 即小数×100"猜测单位，把真实的 **-0.364% 误放大成 -36.4%**（黄金组合A小额亏损/首日<1%必然触发，5 策略当前累计都>1%才没暴露）。根治：数据源显式声明 `return_unit='percent'`，后端直接信任、不再猜测（符合用户"不允许假设"）。
- **坑：venv 无 requests**。venv（backtrader）能跑引擎但不能下载；改为数据下载用 `/usr/local/bin/python3`（有 requests/pandas）、每日引擎用 venv，解释器职责分离。

## 六、验证证据（全部实跑）
1. 每日引擎 dry-run（live-start 2026-06-01→9/18）：**2 笔真实成交** 2026-06-25 BUY 510300 2000股@4.967、2026-07-06 SELL 2000股@4.876 亏 -182 元；nav 79 点首日 50000 末日 49818；**warm-up 泄漏成交=0**；9/18 空仓，净值/成交/持仓自洽。
2. 端到端演练（写 9/18 work_log→rebuild→重启→overview/曲线）：黄金组合A status=running、本金 5 万、total_return **-0.364%**（修正后）、组合 active_count=6/初始 10 万/总 127321.37/+27.32%、曲线 source=work_logs。**演练后已删除演练 work_log+signal 并重跑 rebuild，恢复 9/21 前留空（work_logs/goldcombo 空、signals 0、组合回到 5 策略/5 万/+55.01%、黄金组合A waiting 全 0），无任何假数据残留**。
3. 实盘起点门控：`--date 2026-09-18`（早于默认 9/21）直接拒绝写入。
4. catchup 周日全量实跑：黄金组合A K线增量成功、LOOKBACK 内工作日全部 <9/21 被跳过、rebuild 370 个 ETF signal + 黄金组合A留空、无棘轮写入；`bash -n` 通过；launchd `com.user.quant-daily-catchup` 已加载（工作日 17:45/20:15）。
5. **V24 五年基线复现**（重建数据后 venv 重跑 run_backtest_5y_v24，经 akshare 空桩 wrapper、不改基线脚本）：13 标的全加载、**21 笔与原始完全一致**、+4.5030%/DD 8.18%/final 52251.50（原始 8/17：+4.4311%/DD 8.2434%/52215.55）。**买卖时点 100% 一致 → 重建数据在信号层面与原始等价**；净值差 0.07pp 源于新浪前复权历史价随基准日/分红的正常微调。
   - 注意：该脚本默认落盘覆盖了 `baseline_ashare_real_5y_v24.json`（目录非 git、无其他副本），新值是当前真实数据的诚实复算；原始指标完整保留在同目录 raw_output.log。每日模拟不依赖此 baseline，不影响周一上线；config note 中 +4.4311% 为 8/17 选型历史值，暂保留，是否更新口径由用户决定。
6. 双端截图（手机可经 Tailscale 打开，HTTP 200）：`screenshots/gcprep_01_desktop_top.png`、`gcprep_02_desktop_goldcombo_card.png`、`gcprep_03_mobile_top_316.png`、`gcprep_04_mobile_goldcombo_316.png`。316px 下 innerWidth=scrollWidth=316（无水平溢出），黄金组合A桌面/手机均诚实显示"待启动·NO_DATA·未启动每日模拟·回测不进入实盘"，收益对比注明"黄金组合A未启动每日模拟(留空)"。

## 七、待用户拍板：本金口径（技术已按策略原生 5 万实现）
- V24 策略 `setcash(50000)`、caliber 明确"5 万本金锁死、20%仓位×5 只占 95%"。
- 若用 1 万：单只 20%=2000 元，600519 茅台约 1500 元/股×100=15 万/手、000333 美的约 8400 元/手都买不起，信号严重失真；5 万（单只 1 万）ETF/美的可交易（茅台仍买不起，属客观）。
- 组合口径：当前 5 个 ETF 各 1 万=初始 5 万；加入黄金组合A 5 万后**组合初始变为 10 万（6 策略）**，顶部组合收益率分母随之改变。config/overview/live_data 三处已统一按 5 万实现。

## 八、周一 2026-09-21 收盘后验收点
1. `~/.hermes/logs/daily_catchup.log` 出现黄金组合A K线更新 + 9/21 真实模拟成功；
2. v24 数据更新到 9/21；`work_logs/goldcombo/goldcombo_2026-09-21.json` 自动生成（JSONL 两行）；
3. `signals/goldcombo_2026-09-21.json` 生成；前端黄金组合A卡由"待启动"转"运行中"；
4. 首日大概率空仓/0 成交/净值 5 万/live_days=1（信号稀疏，属真实，不是 bug）；
5. 出桌面 + 316px 手机截图（放 screenshots/ 给 Tailscale URL）。
- 兜底：若 17:45 数据源未更新，20:15 那次会自动补跑（K线闸门保证不用旧数据假装当日）。

## 九、环境铁律（沉淀）
- 5 个 ETF 策略/daily_runner/rebuild/数据下载：`/usr/local/bin/python3`（3.14，有 requests/pandas，无 backtrader）。
- 黄金组合A回测/每日引擎：`/Users/junze/qixing_strategy/venv/bin/python`（backtrader 1.9.78.123 + pandas，**无 requests/akshare**；脚本内对 akshare 注入空桩，只走本地 CSV）。
- 跑任何 quant/hermes Python 前：`export NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""`。
- 重启：`pkill -f real_data_server_v2.py`；`nohup /usr/local/bin/python3 api/real_data_server_v2.py > /tmp/quant_server.log 2>&1 &`（launchd ai.quant.flask 也会保活；get_latest_signal 每次请求读盘，rebuild 后理论上无需重启即可见新 signal）。
