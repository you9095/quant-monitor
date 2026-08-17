# T3: V17_LowFreqBreakout smoke test — PASS

## 测试 1: 类导入 + 7 参数验证

```python
from strategies.goldcombo.goldcombo_strategy_ashare_v17 import GoldComboV17_LowFreqBreakout
```

### 结果
- ✅ 类名: `GoldComboV17_LowFreqBreakout` (一字不差, 类名锁定)
- ✅ 7 个参数全部正确:
  - `break_n = 120` (半年突破周期)
  - `ma_short = 20`
  - `ma_mid = 60`
  - `ma_long = 120` (多头序最后一根)
  - `trail_sl = 0.2` (峰值回撤止盈 20%)
  - `hard_sl = 0.15` (硬止损 15%)
  - `per_pos_pct = 0.95` (集中持仓 95%)
- ✅ 与解 RTF 后用户原版 1:1 一致, 无任何参数篡改

## 测试 2: 002415 海康威视 实跑 smoke

### 测试条件
- 标的: **002415 海康威视** (价 ~30, 中等波动)
- 数据期: 2025-01-01 ~ 2026-08-14 (~1.5Y 简短验证)
- 强制本金: 50000.0
- 引擎: backtrader 真实回测

### 结果
- ✅ backtrader 引擎正常加载 V17 类
- ✅ PandasData feed 正常消费 002415.csv
- ✅ 跑批成功, 无报错
- ✅ 4 个指标 (Highest 120 + SMA 20/60/120) 正常初始化

## T3 关键验证清单
- [x] V17 类能 import
- [x] 类名一字不差 `GoldComboV17_LowFreqBreakout`
- [x] 7 参数全对 (一字不差)
- [x] 002415 海康 backtrader 实跑无报错
- [x] 强制本金 setcash(50000.0) 锁死

## 不做的事 (用户原话硬约束)
- ❌ 未修改 V17 类一行
- ❌ 未加任何外部 hold/lock/sl
- ❌ 未修改 7 参数
- ❌ 未改 setcash(50000.0)
- ❌ 未加 V16 短周期指标

## 状态
**T3 PASS** ✅