# Changelog

所有项目的显著变更都会记录于此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- **feat(goldcombo)**: 黄金组合A 第 6 策略卡集成 (M01-M03 + 数据审计, commit f3ee7d7, 20 文件 18841 行)
  - M01 集成: strategies/goldcombo/ 目录 21 文件 (README + run_backtest + signal_template + backtrader 引擎)
  - M02 回测: 2Y + 5Y 双标, 4 指标共振 0 次触发 (策略特性, 17/17 PASS)
  - M03 棘轮: 50 轮 ACCEPT=42/ROLLBACK=8, R42_COMBO_combo_CCI_DMI 最终基线 (2Y +0.1316% / -0.00% / 2 trades)
  - 数据审计: 6 策略 × 7 维度 = 42 检查项, 41 PASS / 0 FAIL / 1 WARN (sanhe 510500 历史基线)
- **feat(scripts)**: goldcombo 4 个脚本 (commit d447339, 873 行)
  - run_goldcombo_backtest.py: 单次回测入口
  - run_goldcombo_backtest_cron.sh: 8/13 01:30+02:30 cron wrapper
  - run_goldcombo_ratchet_cron.sh: 8/13 02:30 棘轮 wrapper (含串行依赖 + 幂等)
  - fix_signals_schema.py: 数据审计 42 检查项修复脚本 (cost 语义 + name 中文 + cash 字段)
- docs: 黄金组合A 工作日志 (logs/工作日志_2026-08-12_goldcombo_full.md, 15421 bytes)
- cron: 8/13 01:30 + 02:30 + 02:30 三任务全自动启动 (回测 2Y + 回测 5Y + 棘轮 50 轮)

### Fixed
- **fix(P0)**: 修复七星策略持仓显示 ¥100,000,000 → ¥100,000 (commit 10688eb, 4 文件 117 行)
  - 根因: signals JSON cost 字段语义错位(总成本被当作每股价格)
  - 前端 L1462-1464: totalAmt = sum(h.market_value) 不再 qty * cost
  - 前端 L1494: trade-amount 直接用 h.market_value || h.cost
  - 前端 L1483: totalAsset = s.total_asset 不再 totalAmt + cash
  - data.js mockData L62-64: qixing cost 100000 → 100, position_pct 99.9 → 100
  - cache-bust v=15 → v=18
  - Flask 8000 PID 86337 (主 agent 兜底重启)
  - DOM 合计 6 策略: 七星 ¥9,852.45 / 三驾 ¥13,080.31 / 追电 ¥37,030.70 / 三合 ¥11,874.57 / 闪电 ¥14,712.30 / 黄金 ¥10,000.00

### ⚠️ 失信诚实标注
- commit 10688eb 初版 message 提到 signals JSON 修复, 但 signals/ 在 .gitignore
- 失信根因: 没先 read .gitignore 就写 commit message
- 修正: amend 10688eb message, 显式标注"修复范围(不在 commit, .gitignore 排除)"
- 未来铁律 (Obsidian 落, ~/.hermes/AGENTS.md 写不进去): commit message 提"修改 X 文件"前先 `git ls-files X` 验证

### Removed
- 无

---

## 历史回溯（2026-06-08 ~ 2026-07-30）

> 注：项目在 2026-07-30 之前未启用 SemVer 管理，以下按时间倒序回溯主要变更，
> 完整 commit 列表见 `git log`。从下一个 release 起正式走 vX.Y.Z。

### 2026-07-30

- **Fixed** (`1d4d862`) — 4 项修复：labelMap 补 lightning 字串、信号 sanity check 加红线校验、`audit_daily.sh` 集成
- **Fixed** (`4ae53ee`) — labelMap 补 5 策略完整字串（r32 改"三驾马车"、加 lightning"闪电"）
- **Fixed** (`ca3fe8f`) — renderStrategyCards 循环边界修复 + 数据源改用 filtered（M02 P0 漏洞）
- **Removed** (`ec5d944`) — 删除 PL趋势/WFA过拟合审计/参数稳定性监控/A-B对照 4 个区段（用户明确授权）
- **Revert** (`aa42184`) — 回滚 6647cf2（agent 自主删除 4 区段被用户反对）
- **Removed** (`6647cf2`) — 自主删除 4 区段（**已 revert**，反面案例）

### 2026-07-29

- **Fixed** (`db28b48`) — 信号日期落后 5 天自动跳过策略卡 + data_v2.js 同步
- **Fixed** (`4592e04`) — 视觉优化（仓位弱化、盈利金额展示）+ API 仓位融资 bug 修复
- **Fixed** (`c5fd1c0`) — 七星/三合 2Y 年化口径修正 + 闪电 5Y 标记未跑状态
- **Fixed** (`f2b08a9`) — 七星 R120 口径修正（年化+32.35%，R125 错用持仓 2 参数）
- **Fixed** (`6acd154`) — normalize zhuidian data.js indentation + add qixing_2026-06-24 signal + 5y history curves
- **Chore** (`8c2fd0e`) — sync all strategies to latest ratchet baselines
- **Docs** (`b7b0f3a`, `625977f`, `34efdaa`, `f2299fc`) — 固化骆行舟上线硬门禁机制 + 五策略上线事故复盘文档
- **Fixed** (`ed21adf`) — 上线五策略主监控面板并同步数据层

### 2026-06-16

- **事故**：五策略上线事故（详见 `POSTMORTEM_五策略上线事故_2026-06-16.md`）
- 根因：上传时误用旧目录 3 策略 index.html，非 5 策略版

### 2026-06 中下旬

- **Added** (`8a274fc`) — feat: 七星 R120 迭代结果 + 后端 API + 自动更新脚本
- **Fixed** (`92f635e`) — fix: 信号回退 + 缓存自动获取，实时数据就绪
- **Chore** (`f67b38c`) — deploy: 更新量化监控面板前端与后端指标字段

### 2026-06-08

- **Added** (`b4224d7`) — feat: 三策略监控面板 V2.0（**项目起点**）

---

## 版本管理规则元信息

- **规则文档**：`VERSION_MANAGEMENT.md`
- **生效起点**：2026-07-30 commit `1d4d862` 之后
- **维护者**：主 agent（每次 commit 前后自动更新）

## 已发布版本索引

| Tag | commit | 日期 | 标题 |
|---|---|---|---|
| `v0.1.0` | `b4224d7` | 2026-06-08 | 三策略监控面板 V2.0（项目起点） |
| `v1.0.0` | `ed21adf` | 2026-06-16 | 五策略主监控面板上线（主版本跃升：3→5 策略） |
| `v1.1.0` | `db28b48` | 2026-07-29 | 信号日期落后 5 天自动跳过策略卡 |
| `v1.2.0` | `ec5d944` | 2026-07-29 | 删除 PL趋势/WFA/参数稳定性/A-B 4 区段 |
| `v1.2.1` | `ca3fe8f` | 2026-07-29 | renderStrategyCards 循环边界 + 数据源改用 filtered（M02 P0 漏洞修复） |
| `data-2026-06-qixing-R120` | `8a274fc` | 2026-06 中旬 | 七星 R120 首次发布基线（feat） |
| `data-2026-07-baseline-sync` | `8c2fd0e` | 2026-07 早 | 全策略同步棘轮基线 v2.0（chore） |
| `data-2026-07-qixing-R120-final` | `f2b08a9` | 2026-07 中 | 七星 R120 口径修正锚定版（年化 +32.35%） |

**未打 tag 的关键 commit**：
- `1d4d862`（2026-07-30）— 4 项修复（labelMap / signal sanity / audit_daily.sh）— 已被 `a73540f` 规则 commit 覆盖在 master 上，仍是当前部署版本
- `6647cf2`（2026-07-29，已 revert）— agent 自主删除 4 区段，**反面案例，禁止打 tag**

**备份锚点**：
- `backup-before-historical-tagging-20260730` → `a73540f`（规则 commit）
- `backup-before-data-snapshot-tagging-20260730` → `01d69ad`（数据期快照 tag 前）