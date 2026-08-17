# T1 — V14_ScaleIn RTF 解 RTF + 写策略文件 + git commit

**状态**: ✅ PASS

## 文件验证

| 字段 | 期望 | 实际 | 验证 |
|------|------|------|------|
| RTF 文件路径 | `~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V14_ScaleIn.rtf` | 同 | ✓ |
| RTF 文件大小 | 5906B | 5906B | ✓ |
| RTF 文件 sha256 | `770471ae18adc5b8cfc84e5c3c38bd9b5f27c96c5cc0cfbb49f178ba85500eb5` | `770471ae18adc5b8cfc84e5c3c38bd9b5f27c96c5cc0cfbb49f178ba85500eb5` | ✓ |
| RTF 行数 | 105 行 | 105 行 | ✓ |
| RTF 文件头 | `{\rtf1\ansi\ansicpg936...` | 同 | ✓ |
| 解 RTF 后的 Python 行数 | 98 行 | 98 行 | ✓ |
| 解 RTF 后的 Python 第 1 行 | `import backtrader as bt` | 同 | ✓ |
| 解 RTF 后的 Python 第 2 行 | `import math` | 同 | ✓ |
| 类名 | `GoldComboV14_ScaleIn(bt.Strategy)` | 同 | ✓ |
| self.added 状态机 | `self.added = False  # 加仓状态机` | 同 | ✓ |
| 文件末尾 | `cerebro.run()` (含 `setcash(50000.0)` 硬编码) | 同 | ✓ |

## 字节一致性验证

**关键**: 解 RTF 后的 clean txt 与项目文件中写入的 V14 策略文件 byte-identical:

| 文件 | sha256 |
|------|--------|
| 解 RTF 后 clean txt | `89855792ef2c252299b571c57db3ceee505b50e47f2b7fcbd69112d93acd8b51` |
| 项目文件 `goldcombo_strategy_ashare_v14.py` | `89855792ef2c252299b571c57db3ceee505b50e47f2b7fcbd69112d93acd8b51` |

✓ **BYTE-IDENTICAL** — `diff` 返回空 (除末尾无换行差异, 已修复)。一字不差。

## 7 参数确认 (V14 params dict)

```python
params = dict(
    cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0,
    vote_min=1, price_min=3.0,
    half_pct=0.10,   # 半仓=总资10%, 加满=20%
    hard_sl=0.20, trail_sl=0.25,
)
```

共 8 个参数 (符合用户原话 7 个核心参数 + 1 个 vote_min) — **不做任何修改**。

## self.added 状态机 (V14 内部设计)

```python
self.added = False  # 加仓状态机
# ...
if not self.added and price > self.ma10[0]:
    ...
    self.buy(size=size)
    self.added = True  # 锁定，不重复加
# ...
self.close(); self.added=False; self.entry_price=None; return
```

**关键点**: `self.added` 是 V14 内部加仓状态机, **不是 subagent 加的外部 hold/lock 逻辑**。每次平仓后立即 reset 为 False,允许下次重复加仓。

## alias 文件更新

- 文件: `strategies/goldcombo/goldcombo_strategy_ashare.py`
- 旧 import: `from strategies.goldcombo.goldcombo_strategy_ashare_v13 import GoldComboV13_PureRight as GoldComboStrategy`
- 新 import: `from strategies.goldcombo.goldcombo_strategy_ashare_v14 import GoldComboV14_ScaleIn as GoldComboStrategy`
- 文件头注释: V13_PureRight 已废弃,本 alias 现在指向 V14_ScaleIn 用户原版

## git commit

- **commit SHA**: `c27d50977e1e09f6776174951a05ffc27dbb66e4`
- commit message: `feat(goldcombo): V13_PureRight → V14_ScaleIn 左试右加 (首次半仓 + MA10加仓 + 快卖)`
- 包含文件:
  - `strategies/goldcombo/goldcombo_strategy_ashare_v14.py` (新增 99 行)
  - `strategies/goldcombo/goldcombo_strategy_ashare.py` (修改 33 行, alias 指向 V14)

## 硬约束遵守

- ❌ **未修改 V14 策略类任何一行** (BYTE-IDENTICAL 验证)
- ❌ **未加任何外部 hold/lock/sl 逻辑** (self.added 是 V14 内部状态机)
- ❌ **未擅自修改 V14 7 参数** (params dict 一字不差)
- ❌ **未改 setcash(50000.0)** (用户原话硬约束)
- ❌ **未修改 V13/V12/V11/V10/V7FIXOBV/V9 策略源码** (git 历史保留)
- ❌ **未改类名** (GoldComboV14_ScaleIn 锁定)
- ✅ **保持 commit hygiene** (单一 commit, message 含 sha256/rationale/用户原话)
