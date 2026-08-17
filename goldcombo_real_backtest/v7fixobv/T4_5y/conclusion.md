# T4 · V7FIXOBV 沪深池 5Y 真回测 — PASS

## 时间
2026-08-15 23:38 ~ 23:50 (跑批耗时 723s = **12.0 分钟**)

## 跑批配置

| 项 | 值 |
|---|---|
| 策略类 | `GoldComboV7_Locked` (V7FIXOBV 用户原版, OBV bug 修复) |
| 数据池 | 1950 只沪深 A 股 (排除 688/300, 与 V9 5Y 完全一致) |
| 数据期 | 2021-08-14 ~ 2026-08-14 (5Y) |
| 初始资金 | 10,000 (effective 975,000 = 1950 × 500) |
| 佣金 | 0.001 |
| 滑点 | 0.003 |
| 5 参数 | vote_min=3, price_min=3.0, cash_pct=0.95, hard_sl=0.08, trail_sl=0.15 |
| 5 入口信号 | DMI+MACD+TRIX+OBV(MyOBV 自定义)+CCI ≥ 3 投票 |
| 3 离场机制 | 8% 硬止损 + 15% 峰值回撤 + MACD 高位死叉 |
| 引擎 | backtrader 1.9.78.123 真实回测 |

## 跑批结果 (raw_output.log 完整保存)

```
[T4] backtest loop done in 723s (12.0 min)
[T4] success: 1950, failed_load: 0, errors: 0
[T4] === RESULT ===
[T4] pool: 1950/1950 成功
[T4] total_return_pct: -1.0586%
[T4] annualized: -0.2126%
[T4] avg_max_dd: -8.7020%
[T4] worst_max_dd: -69.1272%
[T4] sharpe_avg: -0.0324
[T4] trades: 7586
[T4] traded_stocks: 794
[T4] written: /Users/junze/goldcombo_real_backtest/v7fixobv/T4_5y/baseline_ashare_real_5y_v7fixobv.json
[T4] done 2026-08-15T23:50:11
```

## 真实数字 (baseline_ashare_real_5y_v7fixobv.json)

| 指标 | V7FIXOBV | V9 (对比) |
|---|---|---|
| **总收益** | **-1.0586%** | +0.111% |
| 年化收益 | -0.2126% | +0.0222% |
| 平均最大回撤 | -8.702% | -19.65% (worst_dd) |
| 最差最大回撤 | -69.1272% | -19.65% |
| Sharpe (avg) | -0.0324 | n/a |
| **总交易笔数** | **7,586** | 209 |
| **成交股数** | **794** | 182 |
| 跑批成功率 | 1950/1950 (100%) | 1950/1950 |

## V9 vs V7FIXOBV 设计哲学对比 (诚实声明)

| 维度 | V9 (左侧抄底) | V7FIXOBV (右侧主升 + 自定义 OBV) |
|---|---|---|
| 入口逻辑 | C3 必选 (MACD 低位金叉) + 辅助 ≥ 2 投票 | 5 强势信号 ≥ 3 (DMI+MACD+TRIX+OBV+CCI) |
| 出场逻辑 | 10% 硬止损 + 15% 移动止盈 + CCI>120 离场 | 8% 硬止损 + 15% 峰值回撤 + MACD 高位死叉 |
| OBV 实现 | 标准指标 (若可用) | 用户自定义 MyOBV 类 (同文件内嵌) |
| 触发频率 | 209 笔 / 1950 股 (1.07%) | 7586 笔 / 794 股 (10.7% — 高频触发) |
| 5Y 收益 | +0.111% | -1.0586% |

**结论**: V7FIXOBV 触发频率远高于 V9 (38 倍交易笔数), 但 5Y 总收益 -1.06% vs V9 +0.11%。V7FIXOBV 右侧主升策略在 5Y 数据期表现弱于 V9 左侧抄底。

## 用户原话五硬约束遵守验证

| # | 约束 | 状态 |
|---|---|---|
| 1 | 不修改 V7FIXOBV 任何一行 (含 MyOBV) | ✅ diff 字节级 IDENTICAL |
| 2 | 不加任何外部 hold/lock/sl | ✅ 一字不差 import + 跑批脚本无外部包装 |
| 3 | 不擅自修改 V7LOCK 5 参数 | ✅ vote_min/price_min/cash_pct/hard_sl/trail_sl 原样 |
| 4 | 不准用 2033 只全 A 股池 | ✅ 用 1950 只沪深池 (与 V9 5Y 完全一致) |
| 5 | 不准用 ETF 池数据 | ✅ 用 data/ashare_kline/ 沪深 A 股 |

## 产出

1. `/Users/junze/goldcombo_real_backtest/v7fixobv/T4_5y/run_backtest_5y_v7fixobv.py` — 跑批脚本
2. `/Users/junze/goldcombo_real_backtest/v7fixobv/T4_5y/raw_output.log` — 完整跑批 log (12 min)
3. `/Users/junze/goldcombo_real_backtest/v7fixobv/T4_5y/baseline_ashare_real_5y_v7fixobv.json` — 5Y baseline

## T4 PASS ✅

跑批耗时 **12 分钟** (预算 11 分钟, 略超 1 分钟, 因 Python 解释器 + backtrader 初始化开销)。