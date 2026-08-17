# T1 · 解 RTF + 写 V7LOCK v2 策略文件 + git commit — PASS

## 执行结果

| 项目 | 值 |
|------|-----|
| **用户上传文件** | `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V7LOCK.rtf` |
| **文件大小** | 6238 B |
| **格式** | RTF (header `{\rtf1\ansi\ansicpg936\cocoartf2709`) |
| **RTF 行数** | 105 行 |
| **解出 Python 行数** | 98 行 |
| **用户文件 sha256** | `ababa92a4106c26375927d0fa8c3a9c232eee9d996c64749dcc7394d9fd32810` ✅ 与派单预期一致 |
| **解出文件 sha256** | `85f42b63e7c3131c28dd24db4b017744e0decab1ca6f31b033c80bc0048fd9dd` |
| **V7LOCK v1 旧 sha256** | `6e299160b8eaac3d20d42cf04e1879d0fa6ee66a2cef7b1cde055f98cbf30753` |
| **目标文件** | `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py` |
| **目标 sha256 (写入后)** | `85f42b63e7c3131c28dd24db4b017744e0decab1ca6f31b033c80bc0048fd9dd` ✅ |

## 验证清单

- ✅ 用户上传文件是 RTF 格式 (头 `{\rtf1...`)
- ✅ sha256 完全匹配派单预期 `ababa92a...`
- ✅ `textutil -convert txt` 解出 98 行 Python
- ✅ 第一行 `import backtrader as bt` + 第二行 `import math`
- ✅ 类名 `GoldComboV7_Locked(bt.Strategy)` 一字不差
- ✅ 5 参数完整 (`vote_min=3, price_min=3.0, cash_pct=0.95, hard_sl=0.08, trail_sl=0.15`)
- ✅ 5 强势信号 (DMI 多方 + MACD 水上 + TRIX 零上 + OBV 强势 + CCI 强势) → 投票 ≥ 3 → buy
- ✅ 3 离场机制完整 (8% 硬止损 + 15% 峰值回撤止盈 + MACD 高位死叉)
- ✅ 文件末尾 `if __name__ == '__main__':` 完整跑批脚本, 无截断
- ✅ V7LOCK v2 一字不差覆盖 V7LOCK v1 (v1 IndentationError 版)
- ✅ alias 文件 `goldcombo_strategy_ashare.py` 已指向 V7LOCK (subagent #17 已改, 未重复动)

## git commit

```
commit 19f1cde658407e2d16083bca479fc575471951e2 (HEAD -> master)
Author: subagent #18 <auto>
Date:   2026-08-15

    feat(goldcombo): V7LOCK v1 → v2 完整版 (用户重传完整 buy 算法)
```

- 1 file changed, 99 insertions(+)
- create mode 100644 (因为 v1 是 untracked, 这次是首次 commit)
- v1-v9 git 历史完整保留 (c514fdd V9 / 67a5f98 V8final / 413a4b2 v8 / 6d29242 v6)

## 用户硬约束遵守

| 约束 | 状态 |
|------|------|
| 不修改 V7LOCK v2 策略类任何一行 | ✅ 一字不差 cp |
| 不加任何外部 hold/lock/sl 逻辑 | ✅ 未加 |
| 不擅自修改 V7LOCK 5 个参数 | ✅ 完全保留 |
| 不擅自修改 V8final / V9 源码 | ✅ 未动 |
| 不改 v6 / v3 / v4 旧策略 | ✅ 未动 |

## 备注

- V7LOCK v1 在 subagent #17 落盘后是 untracked 状态 (sha256 `6e299160...`), 该版本在 `else: #` 处截断 + IndentationError 跑不通
- 本次 commit 是首次把 V7LOCK 文件纳入 git 历史 (create mode 100644)
- 完整 buy 算法 (`if sum([s_dmi, s_macd, s_trix, s_obv, s_cci]) >= self.p.vote_min:`) 已完整写盘