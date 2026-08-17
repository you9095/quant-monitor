# T1 · 解 RTF + 写 V7FIXOBV 策略文件 + git commit — PASS

## 时间
2026-08-15 23:35

## 用户文件验证

| 项目 | 值 |
|---|---|
| 文件路径 | `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V7FIXOBV.rtf` |
| 文件大小 | 5028 字节 |
| sha256 | `ac13fcae9baa08f3c75a0d77e45c6c01ddf0bba557f790c80bcd99615e741102` ✅ 与预期一致 |
| 行数 (RTF) | 93 |
| 行数 (解出 Python) | 86 |
| 头部验证 | `{\rtf1\ansi\ansicpg936...` (确认 RTF) |

## 解 RTF (textutil)

```bash
textutil -convert txt -inputencoding UTF-8 -encoding UTF-8 \
  -output goldcombo_strategy_v7fixobv_clean.txt \
  "/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V7FIXOBV.rtf"
```

✅ 第 1 行: `import backtrader as bt`
✅ 含自定义 `MyOBV(bt.Indicator)` 类 (在主策略类之前, 内嵌)
✅ 主策略类名: `GoldComboV7_Locked(bt.Strategy)` (一字不差)
✅ 末尾 `if __name__ == '__main__':` 完整跑批脚本 (无截断)

## V7FIXOBV OBV 修复要点

| 项 | v2 (broken) | V7FIXOBV (fixed) |
|---|---|---|
| OBV 实现 | `bt.ind.OBV()` (AttributeError, 标准库无此指标) | 自定义 `MyOBV` 类 (`bt.ind.SumN(bt.Cmp(...) * volume, period=1)`) |
| `__init__` | `self.obv = bt.ind.OBV(self.data)` | `self.obv = MyOBV(self.data)` |
| OBV 信号 | 永远跑不通 | `s_obv = (self.obv.obv[0] > self.maobv[0])` 正常 |

## 策略文件覆盖 (一字不差)

- 目标: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py`
- 写入 sha256: `4c2698af5570d28426a65d63bf11cb56dd51221c7a5fa825342681df2b8163e8`
- 字节级 diff: 与 RTF 解出文件 **IDENTICAL** (0 字节差异)
- 5 参数原样: vote_min=3, price_min=3.0, cash_pct=0.95, hard_sl=0.08, trail_sl=0.15
- 5 强势信号 (DMI/MACD/TRIX/OBV/CCI) + 3 离场机制 (8% 硬止损 / 15% 峰值回撤 / MACD 高位死叉) + 仓位 + buy 算法全部保留
- 未加任何外部 hold/lock/sl 逻辑

## alias 兼容 (不动)

```bash
$ head -10 strategies/goldcombo/goldcombo_strategy_ashare.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[2026-08-15 版本管理 V7LOCK] v8 EatTheBody / V8final / V9 已废弃,本 alias 现在指向 V7LOCK 用户原版。
本 alias 现在指向 V7LOCK (GoldComboV7_Locked, 右侧主升浪追击 5 强势信号 ≥3 投票, 与 V9 左侧抄底设计哲学完全不同)。
...
```

✅ alias 文件指向 V7LOCK (subagent #17 已改, 不重复改)

## git commit (用户 P0 commit hygiene, 单一 commit)

```
[master 40b73a4] feat(goldcombo): V7LOCK v2 → V7FIXOBV 用户原版 (OBV bug 修复)
 1 file changed, 20 insertions(+), 32 deletions(-)
```

- **commit SHA**: `40b73a4e439e01e6c051c84970feeab1e310b7d5`
- v1-v9 git 历史保留 (commit hygiene)
- 未拆 commit, 单一提交

## 产出

1. `/Users/junze/goldcombo_real_backtest/v7fixobv/T1_extract/goldcombo_strategy_v7fixobv_clean.txt` — 解 RTF 后真 Python
2. `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py` — 已覆盖为 V7FIXOBV 用户原版
3. git commit `40b73a4` — V7LOCK v2 → V7FIXOBV

## T1 PASS ✅