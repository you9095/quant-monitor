---
name: monitor-panel-ui-modification
label: 量化监控面板 UI/数据修改经验
version: 1.4
description: AI量化多策略监控面板项目专属UI/数据修改技能；覆盖板块重排、版式优化、中文化、颜色统一、X轴截断、数据bug修复、移动端适配、持仓口径校正，以及数据真实性根治（快照永久禁止、回测/实盘分离、未启动留空、交易日连续性、CDP 316px真机验证）的标准流程和踩坑记录（2026-09-20 更新至坑18、黄金组合A第6策略每日模拟SOP）。
category: ui-modification
author: Doubao Agent
created: 2026-09-13
project: ai_quant_three_strategy_monitoring_panel
---

# 量化监控面板 UI/数据修改经验技能

## 适用范围
仅适用于 `ai_quant_three_strategy_monitoring_panel`，即 `/Users/junze/quant-monitor-local`。

## 项目结构速查

| 组件 | 路径 | 说明 |
|------|------|------|
| 前端主文件 | `index.html` | 单文件，3500+行，CSS/JS/HTML混杂，已按板块分区 |
| 后端服务 | `api/real_data_server_v2.py` | Flask，27个API路由 |
| 启动脚本 | `start.sh` | 启动前检查端口占用 |
| 板块注册表 | `config/modules.json` | 10个板块的id/name/enabled/order/js_functions/backend_apis |
| 颜色定义 | `index.html` `:root` CSS变量 | 6策略颜色全局统一定义 |
| 服务地址 | `http://localhost:8000` | 本地访问 |
| Tailscale地址 | `http://100.104.238.106:8000` | 手机/远程设备访问 |

## 6 策略颜色体系（全局统一，不可随意更改）

| 策略 | sid | CSS变量 | 色值（start→end） |
|------|-----|---------|-------------------|
| 七星策略 | qixing | --qixing-start/end | #3b82f6 → #8b5cf6 |
| 三驾马车 | r32 | --r32-start/end | #10b981 → #06b6d4 |
| 追电策略 | zhuidian | --zhuidian-start/end | #94a3b8 → #64748b（灰色） |
| 三合策略 | sanhe | --sanhe-start/end | #a855f7 → #facc15 |
| 闪电策略 | lightning | --lightning-start/end | #eab308 → #f97316 |
| 黄金组合A | goldcombo | --goldcombo-start/end | #ef4444 → #f87171 |

**铁律**：每个策略的颜色在整个项目中固定。修改策略颜色后，必须同步更新所有板块（策略卡片、卡片顶部彩色条 `.card-header.{sid}`、收益曲线、OOS、收益对比、Daily P&L、AB对照、策略变更日志 `.log-item/.log-strategy.{sid}`、动作条 today-action-strip）。2026-09-14 排查发现追电改灰时曾漏掉 `.card-header.zhuidian`（仍是旧橙 #f97316），改色后必须全局 grep sid 逐一核对，不能只改 :root 变量。

## 动作标签中文映射（全局统一）

| 英文（CSS类名） | 中文（显示文字） |
|-----------------|-----------------|
| HOLD | 持有 |
| REBALANCE | 调仓 |
| DEFENSIVE | 防御 |
| BUY | 买入 |
| SELL | 卖出 |
| PARAM | 参数 |
| FLAT | 空仓（2026-09-14 新增：无有效持仓时统一显示，灰色） |

**关键原则**：CSS类名保持英文（`.tas-action.HOLD`），显示文字用中文。两者必须分离，不能把CSS类名也翻译成中文。

**动作-持仓一致性铁律（2026-09-14）**：当策略无有效持仓（holdings 中无 qty>0/weight>0）时，HOLD/REBALANCE/DEFENSIVE 必须统一校正为 FLAT(空仓)，否则会出现"顶部显持有、持仓区却无持仓"的左右矛盾。有效持仓判定：`holdings.filter(h=>(h.qty!=null&&h.qty>0)||(h.weight!=null&&parseFloat(h.weight)>0))`。前端字段是 `s.holdings`/`h.qty`（data.js transformApiData 已把 API 的 positions/quantity 映射成 holdings/qty）。

## 常见修改场景标准操作

### 场景1：板块重排（移动板块位置）

1. 在 `index.html` 中找到目标板块的 HTML `<section>` 标签
2. 剪切整个 section 块，粘贴到目标位置
3. 检查 CSS 中该板块的样式是否依赖位置（如 `:first-child`）
4. 检查 JS 中是否有按 DOM 顺序获取元素的代码（如 `querySelectorAll('.section')[2]`）
5. 重启服务验证

**踩坑**：板块移动后，JS 中按索引获取元素的代码会失效。优先用 `getElementById` 或 `querySelector('#module-id')`。

### 场景2：X 轴截断（图表从指定日期开始）

1. 找到图表渲染函数（如 `renderNavCurves`、`loadDailyPnlTrend`、`renderOOSChart`）
2. 在数据处理阶段添加日期过滤：`data.filter(d => d.date >= cutoffDate)`
3. 注意：如果数据获取天数不足，截断后数据点会太少。需同步增加获取天数（如 Daily P&L 从 14 天增至 60 天）
4. 检查图表的 `xAxis` 配置是否需要同步修改 `min` 值

### 场景3：全面板中文化

1. 搜索所有用户可见的英文文本（用 Grep 搜索关键词）
2. 中文化覆盖 4 处渲染位置：
   - `renderActionItems`（收益曲线板块动作标签）
   - `renderTradeDetails`（交易明细卡片徽章）
   - `buildCardHtml`（策略卡片 today-action-strip）
   - `renderLogs`（策略变更日志）
3. CSS类名保持英文，显示文字用中文
4. 在 `renderLogs` 中用 `actionClass`（英文，CSS用）和 `action`（中文，显示用）分离
5. 板块级英文别漏（静态标题 + JS 图表文本两处都要改）：
   - 每日盈亏板块：Daily P&L→每日盈亏、累计/每日 P&L tab、Chart.js `title.text`
   - WFA：Walk-Forward Analysis 去掉英文全称（WFA/OOS 作通用缩写可保留）、OOS Sharpe→OOS 夏普比率
   - AB 对照：grid_mode→网格优选、hardcode/baseline→原参数(基准)、backtest→回测、Grid Mode Wins→网格优选胜出、Baseline Wins→原参数胜出、Ties→持平、Total diff_sum→累计差值合计、diff_sum 时序→累计差值时序
   - 字段名/变量名/winner 判断值（grid_mode/baseline/diff_sum）**保持英文**，只改它们的显示文案
6. 中文化后顺手核对标题里的策略数（如"4 策略"在 qixing 加入后应为 5），静态文案不会自动更新

### 场景4：颜色统一（修改策略颜色）

1. 修改 `:root` CSS 变量中的色值
2. 同步更新所有板块中的硬编码颜色（搜索策略 sid 相关的颜色定义）
3. OOS 板块需特别注意：它可能使用 API 返回的自定义颜色，需强制覆盖为全局颜色
4. 策略变更日志的 `.log-strategy` 类也需同步
5. 重启后逐板块截图验证

### 场景5：后端数据 bug 修复

1. 先调用 API 获取原始 JSON：`curl -s http://localhost:8000/api/v1/xxx | python3 -m json.tool`
2. 核对前端读取的字段路径与实际 JSON 结构是否一致
3. 常见错误：字段在顶层但代码从子对象读取（如 `data.get('diff', {}).get('winner')` 应为 `data.get('winner')`）
4. 修改后重启服务，重新调用 API 验证

### 场景6：服务重启与端口释放

1. 停止服务：`lsof -ti:8000 | xargs kill`
2. 如果端口仍被占用（CLOSED 状态），用 `kill -9 <PID>` 强制释放
3. 启动：`bash start.sh 8000`
4. 健康检查：`curl -s http://localhost:8000/api/v1/health`
5. 等待 3-5 秒后再测试 API（后端启动需要时间）

### 场景7：手机/远程设备访问

1. 确认服务绑定 `*:8000`（所有接口），不是 `127.0.0.1:8000`
2. 确认 macOS 防火墙未拦截
3. 获取 Tailscale IP：`tailscale ip -4`
4. 手机上访问 `http://<tailscale-ip>:8000`，**不能用 localhost**
5. 也可用 MagicDNS：`http://quant-mac.tail959a71.ts.net:8000`

### 场景8：数据真实性根治（快照/回测冒充实盘）—— P0 最高优先级

用户最高 KPI 是"基于真实行情的模拟交易"。详见项目根 `PROJECT_RULES.md` 规则 7。排查/修复 SOP：

1. **唯一直实源**：每日数据只来自 `~/.hermes/work_logs/<sid>/<sid>_YYYY-MM-DD.json`（七星用 `_fusion`），由 `~/.hermes/scripts/p7/daily_runner_v2.py --date D --strategy all --skip-fetch` 对当日真实 K 线切片产出。曲线 builder 只能读 work_logs，零插值。
2. **搜并清除一切兜底/填充**：`grep -rnE "fallback|interpolat|forward.?fill|signal_fallback|evidence|backtest_total_return|random\." api/ scripts/ index.html`，凡出现在"实盘数字位"（组合 total_asset、卡片市值/收益、实盘曲线）一律视为 P0；**没有真实数据就留空（null/不画点/不计入组合），绝不填充**。
3. **回测/实盘分离**：`backtest_*` 字段（回测本金/收益/夏普/回撤/交易数）永远不允许进入实盘卡片、组合汇总、实盘曲线；`live_total_pnl==0` 时禁止用 `backtest_total_return` 折算"等效实盘"。
4. **未启动策略（live_days=0，如 goldcombo 黄金组合A）**：`status=not_started`，所有实盘字段=0、不计入 active_count/初始资金/分母；卡片灰色"未启动"徽章 + 盈亏区"—"。
5. **交易日连续性**：交易日历取 `~/qixing_data/etf_kline/510300.csv`；每个在跑策略 work_logs 必须覆盖全部交易日，零缺口/零 0 字节/周末不误跑。补齐用"当前上线参数+固定 1 万本金+真实历史 K 线"重跑，再 `rebuild_signals_from_worklogs.py`。
6. **三处自洽断言**：daily_pnl 累计末值 == live_curves 末值 − 1 万本金 == 组合分项；初始资金 == active_count×10000；`data_source` 唯一为 work_logs。
7. 网络铁律：跑任何 hermes/quant Python 前 `export NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy=""`。

## 踩坑记录

### 坑1：400px 高度全局化
**现象**：用户要求"收益曲线板块高度400px"，初次实现时把 `max-height: 400px` 加到了所有策略卡片上，导致所有卡片被压缩。
**正确理解**：400px 仅针对收益曲线板块的**.action-items**和**.trade-grid**，且是**每行**400px，不是整个板块。
**教训**：范围限定词是硬约束，不能泛化。修改前确认"哪个元素"的"哪个维度"。

### 坑2：中文竖排丑陋
**现象**：默认精简视图中，动作徽章和策略名水平排列，中文策略名被挤压成逐字竖排。
**解决**：改为上下版式（`flex-direction: column`），动作徽章在上、策略名在下。
**教训**：中文文本在窄容器中水平排列会导致字符竖排，应优先使用上下版式。

### 坑3：CSS类名中文化导致样式失效
**现象**：把动作标签的英文（HOLD/REBALANCE）直接改成中文后，CSS 样式（`.tas-action.HOLD`）不再匹配。
**解决**：CSS类名保持英文，显示文字用中文，两者分离。
**教训**：中文化只改用户可见的显示文字，不改代码标识符（CSS类名、变量名、函数名）。

### 坑4：OOS板块颜色与全局不一致
**现象**：OOS图表使用API返回的自定义颜色，与其他板块的策略颜色不一致。
**解决**：在OOS图表渲染时强制覆盖颜色为全局CSS变量定义的颜色。
**教训**：颜色全局统一是系统性规则，每个板块都要同步。API返回的颜色不可信，必须以前端全局定义为准。

### 坑5：AB对照KPI全0
**现象**：AB对照KPI显示grid_wins=0, ties=4，与历史数据严重不符。
**根因**：后端读取winner字段路径错误（`data.get('diff', {}).get('winner')`，实际winner在顶层）。
**教训**：数据异常时先打印原始JSON结构，再核对读取路径。不要假设字段位置。

### 坑6：端口CLOSED状态无法释放
**现象**：`kill <PID>` 后端口仍被占用，`lsof -i:8000` 显示状态为 CLOSED。
**解决**：`kill -9 <PID>` 强制杀死，必要时连杀两次。
**教训**：Flask开发服务器在某些情况下不会正常释放端口，需要强制杀死。

### 坑7：占位元素复用真实class导致计数错误（持仓"1只↔无持仓"矛盾）
**现象**：空仓策略默认精简视图显"持仓1只"，展开详情却"无持仓"，自相矛盾。
**根因**：无持仓时生成的占位行用了真实行 class `holding-row`，而精简视图用 `querySelectorAll('.holding-row').length` 数持仓，把占位行也数成1只。
**解决**：占位行改用独立 class `holding-empty`；统一 validHoldings=filter(qty>0||weight>0)；空仓动作 HOLD/REBALANCE/DEFENSIVE 校正为 FLAT。
**教训**：占位/空状态元素绝不能复用真实数据元素的 class，否则一切 querySelectorAll 计数都会出错。

### 坑8：异常检测字段与图表绘制字段不一致（"8个突变点"误报）
**现象**：收益对比一直显示"检测到8个数据突变点"。
**根因**：图表实际画 returns(累计收益率=cum/capital*100)，异常检测却遍历 values(市值=capital+cum)；账户本金口径切换(10万↔1万)时 values 必然约10倍跳变、returns 却基本连续，于是必然误报。
**解决**：检测改用实际绘制的 returns、跳过 null、阈值改单日>40个百分点；用 is_interpolated 把首个真实点之前的补0置 null 消起始假阶跃。
**严禁**：用"平移桥接"抹平 returns 阶跃——会改终值(lightning 35.77→14.17)与策略卡 total_return 矛盾，真实数据不许为好看而编造。
**教训**：监控/异常检测的字段必须与可视化绘制字段完全一致；数据源标签也要覆盖 evidence 类真实源(goldcombo_real_backtest_evidence)，否则误显"数据源未知"。

### 坑9：内联grid导致移动端媒体查询永远不生效
**现象**：参数稳定性板块迭代多版，手机端始终5列挤爆，媒体查询像没写一样。
**根因**：容器 HTML 写了内联 `style="grid-template-columns:repeat(5,1fr)"`，内联样式优先级高于 @media。
**解决**：媒体查询里用 `#xxx{grid-template-columns:1fr !important}` 覆盖（手机单列/平板2列/桌面多列）。同类内联grid：#wfa-cards、#ab-comparison-kpi、#ab-comparison-cards、#param-stability-cards。
**教训**："反复适配却不生效"第一反应查元素有没有内联 style；覆盖内联必须 !important。

### 坑10：外层容器padding顶偏内部贴边装饰条（彩色条偏移）
**现象**：策略卡顶部4px彩色条与卡片边缘偏移几像素、像悬浮在中间，从项目初期就存在。
**根因**：手机端 @media 给整张 `.strategy-card{padding:16px}`，把内部第一个子元素 .card-header 向内向下顶偏。
**解决**：外层卡片 padding:0，内边距只加内容区 `.card-body`；.card-header 显式 width:100%/flex-shrink:0/margin:0。
**教训**：要贴边的装饰条/色带，最外层容器不能有 padding，padding 只能加在内容区。

### 坑11：手机端"样式不更新/内容挤左"真凶是水平溢出而非缓存
**现象**：手机清缓存、重启浏览器、重启 Tailscale 后仍是旧样式，内容全挤左侧贴边。
**根因**：某元素(如 .topbar-meta flex-wrap:nowrap)宽度超过视口，scrollWidth(474)>innerWidth(316)，整页按更宽宽度渲染、屏幕只显一部分，看起来像"旧样式/挤左"。
**排查**：页面加临时调试条显示 innerWidth vs scrollWidth，scrollWidth 更大即水平溢出；遍历 getBoundingClientRect 找 right>vw 的元素。修复：html,body overflow-x:hidden+max-width:100vw，nowrap 元素改 flex-wrap:wrap。
**教训**：用户已明确否定"缓存"解释时不要反复回到缓存；先用 scrollWidth-innerWidth 量化判断水平溢出。

### 坑12：改策略颜色后漏改散落的颜色映射表（追电灰改不干净）
**现象**：`:root` 变量和策略卡都改了，hover 光晕、AB 对照仍显旧橙色。
**根因**：同一策略颜色在全文件有多处**硬编码副本**，改 `:root` 不会联动。追电已知同步点：`:root` 变量、`--shadow-glow-<sid>` 光晕、`.card-header.<sid>`、`.log-strategy.<sid>`、收益曲线 colors、WFA/nav 各 colors 对象、AB 板块 `sidColors` 对象。
**解决**：改色后必须 `grep -n "<sid>" index.html | grep -iE "#hex|rgba"` 逐处核对；再 `grep 旧色值` 确认剩余的都是"非该策略"的合理用途（如闪电渐变、全局警告色、AB baseline 语义色）。
**教训**：颜色全局统一是铁律，颜色定义是"多副本"而非单一来源，靠 grep 兜底而非只改变量。

### 坑13：grid `1fr` 被长内容撑成不等宽列，窄列中文逐字竖排
**现象**：316px 下 AB 的 KPI 两列宽度不等（79px/173px），窄列里"网格优选胜出"逐字竖排成 5 行。
**根因**：`repeat(2,1fr)` 等价 `repeat(2,minmax(auto,1fr))`，列的最小宽是内容 min-content；某张卡有长数字（+4,914.9）就把该列撑宽、兄弟列被压窄；中文每个字都可断行，于是在窄列逐字换行。
**解决**：①列定义改 `repeat(N, minmax(0,1fr))`（min 设 0 才真正等宽）；②grid 子项 `.risk-card{min-width:0}`；③不该换行的短标签 `.tab/.risk-title{white-space:nowrap;flex-shrink:0}`，配合父级 `flex-wrap:wrap` 整体换行；④窄屏收窄卡片 padding（24px→12px）给内容腾宽。
**教训**：grid 等宽不要用裸 `1fr`；中文竖排先量列宽是否相等，minmax(0,1fr)+min-width:0 是标准解。

### 坑14：快照/插值把旧数据假装成当日真实数据（2026-09-20 P0，项目长期数据混乱唯一根源）
**现象**：多策略反复"数据陈旧 N 天"，面板却仍显示连续数据；用户多次质疑真实性。
**根因**：缺数据时走 `signal_fallback`、`_linear_interpolate`、沿用最近一天信号，制造"每天都有数据"的假象；且没有任何强校验阻断。"每天数据都一样/连续"本是极易验证的快照特征，却长期没被设为断言。
**解决**：删除一切插值/fallback/evidence 兜底；曲线纯读 work_logs、缺失日 null（spanGaps=false 断线）；无真实数据就留空。立 PROJECT_RULES 规则 7。
**教训**：越是简单可验证的不变量（每日数据应变化、交易日数==日历天数、data_source 唯一）越要写成自动化断言；任何 fallback/interpolate/默认值出现在实盘数字位都是 P0，宁可留空报错。

### 坑15：回测值冒充实盘（goldcombo 黄金组合A 未启动却计入组合）
**现象**：从未接入每日模拟、只有棘轮回测的 goldcombo，卡片显"运行中/当前市值¥100,000/交易92笔/收益11.5%"，还被折算进组合（一度初始6万、收益47.76%）。
**根因**：overview/portfolio 在 `live_total_pnl==0` 时用 `backtest_total_return` 折算"等效实盘 pnl"，回测本金 100K、回测交易数被摆到实盘数字位；evidence 回测净值（backtrader，2021~2026）还被 `_build_goldcombo_curve_from_evidence` 拿来冒充实盘曲线。
**解决**：定义 `live_active=live_days>0`，未启动策略所有实盘字段=0、不计入组合/分母，`status=not_started`，卡片灰色"未启动"+盈亏区"—"；删除 evidence 死代码；前端唯一真实源判 work_logs，empty 留空。
**教训**：回测（参数迭代）与实盘（每日模拟）字段必须物理隔离，`backtest_*` 永远不进实盘数字位；"有信号文件"不等于"在跑每日模拟"，必须看 live_days。

### 坑16：CDP 设备模拟报 Session not found 是参数传法错误，不是 CDP 不可用
**现象**：`bu.cdp("Emulation.setDeviceMetricsOverride", {...})` 报 `Session with given id not found`，一度误判"CDP 不可用"转用 iframe（截图又不可靠）。
**根因**：`bu.cdp(method, session_id=None, **params)` 的第二个位置参数是 `session_id`，把 dict 当位置参数传就被当成 session id。
**解决**：参数全部用关键字传：`bu.cdp("Emulation.setDeviceMetricsOverride", width=316, height=740, deviceScaleFactor=2.625, mobile=True)`，设完 navigate 生效；恢复用 `Emulation.clearDeviceMetricsOverride`。
**教训**：工具报"session/target not found"先核对函数签名与参数位置，别急着否定整条技术路线。

### 坑17：调度脚本把回测结果 --output 写进 work_logs（调度级回测冒充实盘，2026-09-20）
**现象**：work_logs/goldcombo 里出现 3 个 2.58MB 大文件（goldcombo_2026-09-17/18/20.json），内容是棘轮回测 log（version 3.0_ashare、50 rounds），黄金组合A长期"看起来有每日日志、实则全是回测"。
**根因**：`scripts/daily_catchup_runner.sh` 旧第 5 步每个交易日盘后 `nohup python goldcombo_ratchet_ashare.py --output-path "$WORK_LOGS/goldcombo/goldcombo_<今日>.json" &`——**回测脚本产物路径直接指向每日 work_logs 目录**，下游 rebuild/overview 就把它当真实每日数据。代码层做了回测/实盘分离，却漏了调度层。
**解决**：删除 catchup 该步；误置文件归档 `strategies/goldcombo/ratchet_archive/misplaced_worklogs/`（不删可追溯）；棘轮回测不再挂每日调度，输出只许留 strategies/goldcombo/。黄金组合A改走独立每日引擎（见下文 SOP）。
**教训**：回测/实盘隔离三道闸都要审——①代码字段（坑15）②数据来源（坑14）③**cron/launchd 调度脚本的 --output/输出路径**。任何回测/棘轮脚本都不得写 `~/.hermes/work_logs/`；排查"某策略每日数据可疑"必须 grep 调度脚本里指向 work_logs 的写操作。

### 坑18：收益率单位靠数值猜测，真实的 -0.364% 被放大成 -36.4%
**现象**：黄金组合A接入演练累计亏 -182 元、收益率本应 -0.364%，overview 却显 -36.4%（放大 100 倍）。
**根因**：`live_data._normalize_return_pct` 启发式"绝对值<1 且≠0 即小数，×100 转百分比"，但 -0.364 是**真实百分数**（绝对值本就<1%）被误判。5 个 ETF 策略当前累计都 >1% 没触发，黄金组合A小额/首日必然踩中。本质是"靠数值猜单位"的假设，无法区分 0.5% 与 0.5(=50%)。
**解决**：rebuild 的 signal 显式写 `return_unit='percent'`；overview/portfolio 见标记直接 `float(raw_tr)` 信任，不再归一化猜测。
**教训**：单位/口径绝不能靠数值范围启发式推断（"不允许假设"）；生产端显式声明单位、消费端直接信任。首日 0%、小额 ±0.x% 是真实常见状态，转换必须覆盖。

## 黄金组合A（goldcombo）每日真实模拟 · 第 6 策略运维 SOP（2026-09-21 上线）

- **定位**：黄金组合A策略 V24 `DMAStrategy`（DMA 金叉死叉 + 量1.5× + RSI30-70 + MA200 三重过滤，5 万本金锁死、最多 5 只各 20%，信号极稀疏 5 年 21 笔）。棘轮/5Y 回测只做参数迭代，**绝不产出每日信号**（规则7 + 坑17）。
- **解释器/依赖分离（铁律）**：
  - 5 个 ETF 策略 / daily_runner / rebuild / **数据下载** 用 `/usr/local/bin/python3`（有 requests/pandas，无 backtrader）。
  - 黄金组合A回测 / 每日引擎用 `/Users/junze/qixing_strategy/venv/bin/python`（有 backtrader 1.9.78 + pandas，**无 requests/akshare**；策略 import akshare 但回测路径不调用，脚本内注入空桩、只读本地 CSV）。
  - `fetch_v24_pool_kline.py`（requests）用系统 python；`goldcombo_daily_run.py`（backtrader）用 venv——用错解释器会 ModuleNotFoundError。
- **三个脚本**：
  - `scripts/fetch_v24_pool_kline.py [--full]`：新浪真实日线→`data/v24_{etf,stk,bonds}_kline`，默认增量 120 根、退市不补点；13 标的中 5 转债已全退市（2026 实盘可交易=5ETF+3STK 共 8 个，不擅自换券）。
  - `scripts/goldcombo_daily_run.py --date YYYY-MM-DD [--live-start 2026-09-21] [--dry-run]`：复用 DMAStrategy 不改一字，live_start 前只 warm-up 不交易（脚本内 + catchup 日期比较双门控），set_coc 收盘价成交，写标准 JSONL（morning/afternoon、daily_pnl、positions_before/after、capital=50000、return_unit='percent'、live_start_date）。
  - `rebuild_signals_from_worklogs.py`：6 策略同构，本金 per-sid（5 个 ETF 各 1 万、黄金组合A 5 万），无 work_log 不生成 signal（留空）。
- **调度**：`daily_catchup_runner.sh` 第 4 步（系统 python 更 V24 数据 → venv 逐日幂等补跑，<live_start 跳过、K线未到当日等下次不造假），第 5 步统一 rebuild；launchd 工作日 17:45/20:15（20:15 兜底数据源延迟）。
- **本金口径**：黄金组合A 5 万（setcash 锁死，1 万买不起茅台/美的整手会失真）；加入后组合初始资金 5 万→**10 万（6 策略）**，overview 组合汇总按各在跑策略真实本金求和（active_init），不再是 active_count×10000。
- **首日真实预期**：信号稀疏，周一 2026-09-21 首日大概率空仓/0 成交/净值 5 万/live_days=1，**真实而非 bug**；卡片由"待启动/NO_DATA"转"运行中·空仓"。
- **数据正确性基线**：重建数据后用 venv + akshare 空桩 wrapper 重跑 `/Users/junze/goldcombo_real_backtest/v24/T4_5y/run_backtest_5y_v24.py`，应复现约 21 笔（笔数/买卖时点必须一致；净值随新浪前复权微调 0.0x pp 正常）。注意该脚本默认落盘覆盖 baseline json。

## 移动端验证方法（首选 CDP 真机视口模拟）

用户真机（小米14 Pro）视口仅 **316px**、DPR 2.625（不是典型 390px），布局必须按 316px 验证。

**首选 CDP（2026-09-20 验证可用，最可信）**，在 `plane="bu"` cell 里：

```python
bu.cdp("Emulation.setDeviceMetricsOverride", width=316, height=740, deviceScaleFactor=2.625, mobile=True)
bu.navigate(url); bu.wait_for_load(); time.sleep(5)
# 断言 innerWidth==316 且 matchMedia('(max-width:768px)').matches==True，再逐屏 scroll + screenshot
bu.cdp("Emulation.clearDeviceMetricsOverride")  # 恢复桌面视口
```

- **参数必须用关键字传**（`width=`/`height=`/`deviceScaleFactor=`/`mobile=`）；把 dict 当第二个位置参数会被当成 `session_id`，报 `Session with given id not found`——这正是此前误判"CDP 不可用"的真正原因（见坑16）。
- 设完必须重新 `navigate` 才生效；截图尺寸变为 316×740，媒体查询真实触发，图表/grid/圆角全部按真机渲染。

**iframe 法已弃用**（仅 CDP 真不可用时测布局数值）：注入 316px fixed iframe 可读 `innerWidth/scrollWidth`、遍历 `getBoundingClientRect()` 判溢出，但 **`bu.screenshot` 对 iframe 合成不可靠——只绘制 iframe 顶部约 45px、下方透底，且 iframe 无独立 ref、不能元素截图**，不能用于交付出图。

通用：截图临时文件 shot.png 每次覆盖，必须立即 `cp` 到 `screenshots/`。

## 修改后验证清单

### 基础项
- [ ] 服务重启成功，`http://localhost:8000` 可访问
- [ ] 健康检查 `http://localhost:8000/api/v1/health` 返回 HTTP 200
- [ ] 修改的板块视觉效果正确（截图验证）
- [ ] 其他板块未受影响（快速浏览全页）
- [ ] 图表数据加载正常，无空白或报错
- [ ] 浏览器控制台无项目侧 JS 错误（chrome-extension:// 的报错与本项目无关，可忽略）
- [ ] 如涉及后端修改，API 返回数据正确

### 数据一致性项
- [ ] 6 策略颜色在所有板块一致；**改色后 `grep <sid>|grep -iE '#hex|rgba'` 核对全部颜色副本**（:root/shadow-glow/card-header/log-strategy/各曲线 colors/AB sidColors）
- [ ] 中文显示正确、无英文残留（用户可见文字）；字段名/变量名/CSS 类名保持英文
- [ ] 静态标题里的策略数与实际一致（qixing 加入后为 5，静态文案不会自动更新）
- [ ] 持仓类改动：顶部标签 / 精简视图 / 展开详情三处动作与持仓数一致
- [ ] 异常检测/统计所用字段与图表实际绘制字段一致（returns vs values 之鉴）

### 数据真实性项（P0，每次涉及数据必跑）
- [ ] 每条曲线 `data_source` 唯一为 `work_logs`；出现 signal_fallback/evidence/插值即 🚫 异常
- [ ] 组合 `active_count` 只数 live_days>0；初始资金 == 各在跑策略本金之和（5 个 ETF 各 1 万 + 黄金组合A 5 万=10 万，不是 active_count×10000）；未启动策略全 0 且不计入
- [ ] 每个在跑策略 work_logs 交易日数 == 交易日历（510300.csv）天数，零缺口/零 0 字节
- [ ] daily_pnl 累计末值 == live_curves 末值−1万本金 == 组合分项，三处自洽
- [ ] 实盘数字位无任何 backtest_* 折算/兜底；无真实数据一律留空，不填充、不插值
- [ ] 补齐历史只能用 daily_runner_v2 + 真实 K 线 + 当前上线参数 + 1 万本金，补齐后 rebuild signals

### 移动端必做（真机视口 316px，不是 390）
- [ ] CDP `setDeviceMetricsOverride(316,740,2.625,mobile=True)` 后 `scrollWidth - innerWidth ≤ 0`（水平溢出会伪装成"样式没更新/内容挤左"）
- [ ] 逐 section 遍历 `getBoundingClientRect()`，无元素 right > 视口宽
- [ ] 多列 grid 各列**等宽**（裸 `1fr` 会被长内容撑成不等宽、窄列中文逐字竖排，须 `minmax(0,1fr)`+子项 `min-width:0`）
- [ ] 短标签（tab/badge/title）单行不竖排（`white-space:nowrap`）
- [ ] 桌面视口（clearDeviceMetricsOverride）回归：移动端 !important 改动没有破坏桌面多列布局

## 触发词

- 修改监控面板、调整UI、改板块位置、中文化、翻译英文
- 改颜色、统一颜色、策略颜色、X轴截断、改日期范围
- AB对照数据异常、KPI不对、数据失真
- 手机打不开、远程访问、Tailscale访问
- 中文竖排、文字竖着排、grid不等宽、卡片一宽一窄、列宽不一致
- 持仓矛盾、默认与展开不一致、数据突变点误报、彩色条/色条偏移
- 水平溢出、内容挤左边、316px、手机端适配、样式不更新
- 快照、数据真实性、数据陈旧、回测冒充实盘、回测实盘分离、未启动策略、goldcombo留空、交易日缺口、信号缺失、CDP真机模拟、黄金组合A每日模拟、goldcombo_daily_run、V24 DMAStrategy、venv解释器分离、调度回测写work_logs、收益率单位return_unit、5万本金
- 保存经验、沉淀技能、UI修改经验、工作日志、单文件记忆、Obsidian
