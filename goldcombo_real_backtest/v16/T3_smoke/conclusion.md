# T3 · smoke test — PASS

## 1) import + 5 参数验证
- **类名**: `GoldComboV16_ChannelBreakout` ✅
- **5 参数 (一字不差)**:
  - `break_out=20` ✅
  - `break_down=10` ✅
  - `ma_filter=50` ✅
  - `atr_period=14` ✅
  - `risk_pct=0.02` ✅

## 2) 002415 海康威视 单股烟测
- 数据期: 2022-01-01 ~ 2026-08-14
- 数据行数: 1117
- 起始资金: 50,000.00
- 最终资金: 43,114.80
- **总收益: -13.77%**
- V16 触发 + 离场 + ATR 定仓三机制均正常工作

## T3 结论: **PASS**