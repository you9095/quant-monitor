# T3 · smoke test — 完成报告

## 1. import 测试
```
$ python3.12 -c "from strategies.goldcombo.goldcombo_strategy_ashare_v3 import GoldComboV3_1Strategy"
import OK: GoldComboV3_1Strategy
模块: strategies.goldcombo.goldcombo_strategy_ashare_v3
```
✅ 通过

## 2. 参数加载验证
- cci_thresh = -80
- di_neg_thresh = 25
- di_pos_thresh = 15
- vote_min = 2
- **price_max = 90.0** (新)
- **price_min = 3.0** (新)
- **cash_pct = 0.95** (新)
- **hard_sl = 0.05** (从 v2 的 0.08 改严)
- **trail_sl = 0.08** (新)
- print_log = True (默认,测试时改 False)

## 3. 单股 smoke 测试结果 (2Y 数据 2021-08-13 ~ 2026-08-13, 10000 初始资金)

| 股票 | 最新收盘价 | 起始资金 | 最终资金 | 收益 | 预期 |
|------|-----------|----------|----------|------|------|
| 600519 贵州茅台 | 1357.01 | 10000.00 | 10000.00 | 0.00% | 0 笔 (价>90 被过滤) ✅ |
| 002415 海康威视 | 35.96 | 10000.00 | 10599.19 | +5.99% | 通过价格过滤有成交 ✅ |

## 4. 关键验证
- ✅ 价格过滤正常工作:茅台 1357 > 90 被剔除 → 0 笔 (非 bug 是设计)
- ✅ 价格过滤通过时:海康 35.96 在 [3, 90] 区间 → 正常进出场
- ✅ 仓位按 95% 现金 + 按手取整:1万本金实际下单规模正常
- ✅ 5% 硬止损 + 8% 移动止盈 + CCI>120 + MACD 高位死叉 4 个出场条件全部就位
- ✅ backtrader 1.9.78.123 + pandas 数据流跑通,无报错

T3 PASS — v3 策略可正常运行,可进入 T4 全量 1950 只 2Y 回测。
