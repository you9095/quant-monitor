# 量化监控项目 · 实盘架构定型关键记忆（2026-10-06 里程碑）

> 节点：底层撮合 / 调度 / 部署 / 数据双通道全部跑通，Windows 一键部署落地，正式转入前端 UI/交互打磨。本篇是"当前系统长什么样、哪些不能碰"的速查，改动前先读这里。

## 一、系统定位（最高约束，不可动摇）
- **模拟盘，绝不连接任何券商真实账号 / 资金账号 / xtquant / QMT**。所谓"实盘"= Windows 本机撮合引擎按**真实行情**成交、**真实记账**（真实买卖、佣金/印花税/滑点/T+1），但资金是虚拟的 1 万/策略。
- 六策略各本金 **10000**：qixing 七星、r32 三驾马车、zhuidian 追电、sanhe 三合、lightning 闪电、goldcombo 黄金组合A。
- **任何数据必须标注性质**：实盘模拟(本机真实撮合) / 回测 / UI测试虚拟数据；模拟与实盘数据绝不能相同；未启动留空，禁止快照/前向填充/随机数/回测冒充实盘（PROJECT_RULES 规则2/5/7，P0）。

## 二、双机分工与双仓库
- **macOS**：设计/开发/数据诊断/架构/代码调试；**Windows（主机名"钧泽"）**：实盘运行。用户只在**交易日 13:00–17:00 开 Windows**，节假日/周末不开；拒绝 7×24。
- 代码仓库：`git@github.com:you9095/quant-monitor.git`（master）。
- 数据仓库（私有，唯一真相源，唯一分支 master）：`git@github.com:you9095/quant-monitor-live-data.git`；Mac 本地副本 `/Users/junze/quant-monitor-local/live-data`。
- Windows 路径：代码 `D:\quant-monitor`（venv `D:\quant-monitor\venv\Scripts\python.exe`，Python 3.11.9）；安装期数据通道 `D:\_qm_live`；日志 `D:\quant-monitor-install.log`。**项目必须放 D 盘，不放 C 系统盘。**
- 数据仓库约定：`daily/{YYYY-MM-DD}/{sid}.json`、`latest/{sid}.json`、`_account_state/{sid}.json`、`_run_logs/`、`_deploy_status/{hostname}.json`、`_install_status/{COMPUTERNAME}.txt`、`_reset_marker.json`；交易目录含 `.gitkeep`。

## 三、Windows 三计划任务（schtasks，已验证 REGISTERED）
- `QuantDailyTrade`：onlogon 延迟 3 分钟跑 `daily_task.py trade`（主；窗口工作日 13:00–17:00；流程 更新代码→装依赖→`run_daily_engine.py once`→push 数据→心跳→重启面板）。
- `QuantDailyTradePM`：工作日 15:10 跑同一 trade（收盘兜底，引擎当日幂等）。
- `QuantBootCheck`：onlogon 延迟 1 分钟跑 `scripts/fix_and_report.py`（代码 reset --hard、数据仓库强制对齐、网络自愈、上报，**不交易**）。
- 已删除：QuantExecuteTask(原09:35)、QuantDecideTask(原15:30)。
- **成交逻辑（once 单段式）**：拉历史收盘算动量目标 → 取开机时刻最新价（盘中 fund_etf_spot_em 实时 / 收盘后当日收盘 / 缺失用日线收盘兜底，记 `price_source`）→ end_of_day(T+1) → rebalance 真实撮合 → settle 净值 → 写账本；当日幂等（`daily/<today>/<sid>.json` 已有 phase=trade 即跳过）。
- 撮合参数：COMMISSION_RATE=0.00025、MIN_COMMISSION=5.0、STAMP_TAX_RATE=0.0005(仅卖出)、SLIPPAGE=0.001、LOT=100。Broker 在 `api/matching_engine.py`。

## 四、交易日历（2026-10-06 加固，commit 619baec）
- `api/market_data.py::load_trade_dates/is_trade_date`，源 `ak.tool_trade_date_hist_sina()`，缓存 `data/trade_calendar.json`（覆盖全年）；`is_trading_day` 优先用日历，休市日开机也不成交。
- **2026 国庆：10-01~10-07 休市，10-08（周四）节后首个交易日**。

## 五、归零
- `scripts/reset_accounts.py`：步骤0 先 fetch+reset --hard origin/master（防 Mac 落后导致 push 冲突）；六策略重置现金1万/空仓/0成交；清 daily/latest/_run_logs 但**保留 .gitkeep**；保留 etf_cache 与部署心跳；写 _reset_marker；自动 push。参数 `--yes/--dry-run/--no-push`。
- 一次性 at 任务（id 13140844451074）定 **2026-10-06 17:00 Mac 执行**；Mac 未开机则补跑。

## 六、自动化边界（给用户讲清，避免再纠结"为何还要点一次"）
- 全新机器存在引导困境：第一个计划任务无法自己创建自己；创建系统任务受 Windows UAC 限制必须真人点一次。**安装器整台机器一生只跑一次管理员**，V1–V9 反复点是踩坑期，已结束。
- "内容层"（.py 策略/行情/风控/面板/脚本）更新全部走 GitHub 开机自动下发，零点击；"结构层"（改计划任务触发器、装系统组件、换电脑/重装）才需再管理员一次。日常迭代约束在内容层。
- 安装器铁律见 `memory/windows-installer-v9-polyglot.md`（polyglot：1 行 cmd 钥匙 + 全 Python 主体；新文件名绕开 raw 缓存；SSH443 首选）。

## 七、UI 打磨阶段 · 虚拟数据隔离铁律（2026-10-06 新立，极重要）
- 为走查 UI 而造的虚拟数据（约 35 天、全板块）**只能放隔离环境**：独立数据目录或独立本地分支/独立端口；**绝不写入真实 live-data、绝不 push、绝不与实盘账本混**；界面显式标注"UI 测试虚拟数据（非实盘/非回测/非真实盈亏）"；用完整体丢弃。
- 真实面板实盘位在 10-08 首笔成交前保持留空。修 UI 每版截图发用户确认。

## 八、协作规则（强约束）
- 用户说"**开始盯**"才挂监控；挂上后 **1 分钟无信号立即停**（已从2分钟改为1分钟），不空等、不自行盯。
- 观察 Windows 一律读数据仓库心跳，不让用户发截图；连上 GitHub 前是物理盲区。
- 回复：解释的话单独成段、操作清单单独成段，彻底分开；先总后分、大白话+比喻、核心结论先行。
- 追求一个文件一次双击、诊断+修复+安装+自检+上报合一；命令不要出现用户打不出的特殊符号；bat 纯 ASCII + CRLF。
- 存档老规矩：工作日志 `work_logs/YYYY-MM-DD_主题.md`；单文件记忆 `memory/<主题>.md`；知识/Obsidian `knowledge/<中文目录>/`；事故复盘根目录 `POSTMORTEM_*.md`；PROJECT_RULES.md 最高铁律。

## 九、commit 链（代码 master）
v9 成功 e08053e → 调度改造+reset 1f8cf02 → 调度工作日志 2778d49 → 管理员检测/回查/心跳 799bf47 → 交易日历+数据仓库强制对齐+trade_calendar 619baec → reset 加固 34df754。
