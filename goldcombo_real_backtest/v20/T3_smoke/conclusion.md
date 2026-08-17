# T3 · smoke test — V20_NoMA 零均线数值化版

**时间**: 2026-08-16
**任务**: import + 10 参数 + 零 SMA 验证 + 单股触发测试

## 1. import 验证

```
import OK: GoldComboV20_NoMA
```

✅ **PASS**: V20_NoMA 成功从项目位置 import,类名一字不差。

## 2. 10 参数验证 (全部 ✅)

| 参数 | 实际值 | 预期值 | 状态 |
|---|---|---|---|
| break_n | 60 | 60 | ✅ |
| atr_period | 14 | 14 | ✅ |
| atr_multi | 3.0 | 3.0 | ✅ |
| cci_peak | 100.0 | 100.0 | ✅ |
| cci_fall | 80.0 | 80.0 | ✅ |
| trail_sl | 0.35 | 0.35 | ✅ |
| hard_sl | 0.15 | 0.15 | ✅ |
| price_min | 1.0 | 1.0 | ✅ |
| cash_pct | 0.95 | 0.95 | ✅ |
| cool_days | 60 | 60 | ✅ |

**10 参数全对,零修改**。

## 3. 零 SMA 验证 (用户原话硬约束"卖点剔除所有MA")

- `grep -n "bt.ind.SMA\|bt.indicators.SMA" goldcombo_strategy_ashare_v20.py`
- 唯一匹配: 第 9 行 docstring 注释 `【硬性规则 - 全策略无 bt.ind.SMA / MA 】`
- **0 个实际 SMA/MA 指标调用** ✅

V20 仅 3 个指标:
- `bt.ind.Highest(self.data.high, period=self.p.break_n)` — 60日 最高价通道
- `bt.ind.ATR(period=self.p.atr_period)` — ATR(14)
- `bt.ind.CCI(period=14)` — CCI(14)

**零 SMA/MA,纯数值化版本**。

## 4. 002415 海康威视 smoke test (价 ~30, V20 设计特性)

| 指标 | 数值 |
|---|---|
| K 行数 | 1117 |
| 价格区间 | 23.23 ~ 48.06 |
| 起始资金 | 50000.00 |
| 最终资金 | 37222.68 |
| **总收益** | **-25.5546%** |
| **笔数** | **7** (≥3 笔门槛 ✅) |

V20 在 002415 海康 4.5Y 期间触发 7 笔,价 ~30 是 V20 设计的目标价区间。-25.55% 说明 4 离场机制 (15% 硬止损触发频繁) 在 30 元股上偏严格。

## 5. 内部状态 (无外部 hold/lock)

V20 内部状态变量:
- `self.entry_price` — 入场价
- `self.highest` — 持仓期峰值
- `self.cooldown` — 冷却天数 (卖后 60 日禁买,**V20 内部冷却机制**,不是 subagent 加的外部 lock)

**无 self.lock / self.hold / self.lockday 等外部逻辑** ✅

## 6. 结论

- ✅ **T3 PASS**: V20 策略类能成功 import + 实例化
- ✅ **10 参数全对,零修改**
- ✅ **零 SMA/MA 实际调用**(只有 1 次 docstring 注释提及)
- ✅ **强制 5 万本金锁死 + setcash 正常工作**
- ✅ **cooldown 是 V20 内部 self.cooldown 字段**,非外部 hold/lock

**进入 T4 沪深池 5Y 真回测**。
