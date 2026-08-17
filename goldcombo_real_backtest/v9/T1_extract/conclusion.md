# T1 · V9 用户原版策略解 RTF + 写项目 + git commit — PASS

## 验证清单

### 1. V9 用户上传文件验证

| 项目 | 值 |
|------|-----|
| 路径 | `~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第四版V9.py` |
| 大小 | 4575 字节 |
| sha256 | `32f6813d84c0406fef979e0d3372cd4575dabe90403a21e3df54a0c6a927841f` |
| 格式 | RTF (头 `{\rtf1\ansi\ansicpg936\cocoartf2709` 已确认) |

### 2. textutil RTF 解码

- 输入: RTF 源文件 4575B
- 输出: `goldcombo_strategy_v9_clean.txt` 3487B (UTF-8)
- **第一行验证**: `import backtrader as bt` ✓
- **类名验证**: `class GoldComboV8_Final(bt.Strategy):` ✓
- 第二行: `import math` ✓
- 完整 80 行 Python 代码,内容正确

### 3. V9 策略文件写入项目

| 项目 | 值 |
|------|-----|
| 目标路径 | `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v9.py` |
| 大小 | 3487 字节 |
| sha256 (写入后) | `aa3fa8abe605b19ff4797b9a3ddf6a52b763c95bbf4dcde2434c60fa8aebbcb7` |
| sha256 (T1_extract 副本) | `aa3fa8abe605b19ff4797b9a3ddf6a52b763c95bbf4dcde2434c60fa8aebbcb7` |
| **一字不差验证** | ✅ 两文件 hash 完全一致 |

### 4. alias 文件改指向 V9

| 旧 | 新 |
|----|----|
| `from strategies.goldcombo.goldcombo_strategy_ashare_v8final import GoldComboV8_Final as GoldComboStrategy` | `from strategies.goldcombo.goldcombo_strategy_ashare_v9 import GoldComboV8_Final as GoldComboStrategy` |

头注释已同步更新:指向 V9,保留 V8final/V6/v4/v3 git 历史。

### 5. **不修改**项验证 (用户原话硬约束)

- ✅ V9 策略类一行未改
- ✅ 未加任何外部 hold/lock/sl 逻辑
- ✅ 9 个参数一字不差 (`cci_thresh=-70.0, di_neg_thresh=20.0, di_pos_thresh=15.0, vote_min=2, price_min=3.0, cash_pct=0.95, hard_sl=0.10, trail_sl=0.15, cci_exit=120.0`)
- ✅ V8final 策略源码未改 (保留 git commit `67a5f98`)
- ✅ v6/v3/v4 策略源码未改

### 6. git commit

```
c514fddde932d69245d85f32a32e24a1a05bb3f6c
feat(goldcombo): V8final → V9 用户原版 (一字不差, 不准加 hold/lock)
 2 files changed, 96 insertions(+), 14 deletions(-)
```

## V9 vs V8final 真实差异 (主 agent 二次二校确认)

| 维度 | V8final | V9 |
|------|---------|-----|
| 类名 | GoldComboV8_Final | GoldComboV8_Final |
| 9 个核心参数 | 完全一致 | 完全一致 |
| 持仓离场 3 机制 | 10% 硬止损 + 15% 移动止盈 + CCI>120 | 10% 硬止损 + 15% 移动止盈 + CCI>120 |
| 空仓入场 C3 + vote ≥ 2 | 一致 | 一致 |
| 仓位 cash_pct * cash 按手 | 一致 | 一致 |
| **debug 参数** | ❌ 无 | ✅ 新增 (默认 False,不影响主逻辑) |
| **math.isnan 防护** | ❌ 无显式防护 (CSV 缺量 NaN 会触发静默 0) | ✅ 显式防护 (macd/cci/plus_di/minus_di NaN 时 return) |

V9 与 V8final 逻辑 100% 一致, 区别仅 2 个增量:
1. `debug=False` 参数 (不影响回测)
2. `math.isnan` 防护 (DMI=NaN 防御)

## 用户原话三硬约束执行

1. ✅ "必须一字不差地用这个类跑股票池子" — V9 内容 hash 验证通过, 一字未改
2. ✅ "不准加任何外部 hold/lock" — V9 策略类外部无任何包装/拦截/hold/lock/sl 注入
3. ✅ "不准擅自修改 V9 9 个参数" — params dict 完整保留, 9 个参数值与原文一致

## 结论

**T1 PASS** — V9 策略已一字不差写入项目,git commit 单一 commit 已落 (SHA: `c514fddde932d69245d85f32a32e24a1a05bb3f6c`),alias 已切到 V9,无任何外部 hold/lock 注入。