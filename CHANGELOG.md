# Changelog

所有项目的显著变更都会记录于此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 待写

### Changed
- 待写

### Fixed
- 待写

### Removed
- 待写

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

### 2026-06-08 ~ 2026-06-12

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

**未打 tag 的关键 commit**：
- `1d4d862`（2026-07-30）— 4 项修复（labelMap / signal sanity / audit_daily.sh）— 已被 `a73540f` 规则 commit 覆盖在 master 上，仍是当前部署版本
- `6647cf2`（2026-07-29，已 revert）— agent 自主删除 4 区段，**反面案例，禁止打 tag**

**备份锚点**：`backup-before-historical-tagging-20260730` 指向 `a73540f`（规则 commit）