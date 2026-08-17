# T3 · 单股验证 600438 通威股份 — FAIL (V7LOCK v2 OBV blocker)

## 执行结果

| 项目 | 值 |
|------|-----|
| **单股** | 600438 通威股份 (硅料龙头, 沪市主板, 价 10.48~63.99) |
| **数据期** | 2022-01-01 ~ 2026-08-14 |
| **bars 数** | 1107 |
| **跑批结果** | ❌ V7LOCK v2 初始化失败: `AttributeError: module 'backtrader.indicators' has no attribute 'OBV'` |
| **成交笔数** | 0 (策略类在 `__init__` 崩溃, 永远到不了 buy) |
| **能否批量跑 T4** | ❌ **不能** — blocker |

## 验证目标评估

| 目标 | 状态 |
|------|------|
| ❌ 如果 0 笔成交 → 不能批量跑, blocker 报告 | ✅ **达成** — 0 笔, blocker 报告已落 `blocker_report.md` |
| ✅ 如果 ≥ 1 笔成交 → 可以批量跑 | ❌ 未达成 — 0 笔 |
| 关键诚实诊断: 单股 0 笔时不擅自改阈值 | ✅ **达成** — 不擅自改, blocker 报告 |

## 根因

V7LOCK v2 用户原版策略类 (`goldcombo_strategy_ashare_v7lock.py` line 37) 调用 `self.obv = bt.ind.OBV()`, 但 backtrader 1.9.78.123 没有 OBV 实现 (`bt.ind.OBV` 和 `bt.ind.OnBalanceVolume` 都不存在)。

## 关键诚实

- V7LOCK v2 用户原版策略代码一字不差保留在 git commit `19f1cde`
- 不擅自 monkey-patch / 不擅自替换 OBV / 不擅自修改 V7LOCK 任何一行 (用户原话硬约束)
- 不擅自改 backtrader 版本
- 不擅自跑 0 触发回测凑数

## blocker 报告

完整 blocker 上报见同目录 `blocker_report.md`。

主 agent 需要向用户上报, 由用户决策:
- 选项 A: 维持硬约束, V7LOCK v2 标 BLOCKER, 等用户决策
- 选项 B: 升级 backtrader (风险大)
- 选项 C: 子类化替换 OBV (违反"不得修改 V7LOCK 策略类任何一行")
- 选项 D: wrapper strategy monkey-patch (违反"硬性规则全内嵌")

**subagent #18 推荐选项 A** (维持硬约束)。

## T4 状态

**SKIPPED** — T3 单股 0 笔, T4 (1950 只沪深 A 股 5Y 真回测) 不执行。