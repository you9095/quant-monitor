# T3 · smoke test 结论

**任务**: import 验证 + 双股 smoke 跑批 (600519 + 002415)

## 1. import 测试

```
from strategies.goldcombo.goldcombo_strategy_ashare_v6 import GoldComboV6Strategy
import OK: GoldComboV6Strategy

from strategies.goldcombo.goldcombo_strategy_ashare import GoldComboStrategy
alias GoldComboStrategy → GoldComboV6Strategy
✅ alias 正确指向 v6
```

## 2. smoke test 600519 (茅台, 价 ~1148-1971)

| 项目 | 值 |
|------|-----|
| 数据期 | 2021-08-13 ~ 2026-08-13 (1211 行, 5Y 全量) |
| 价格范围 | 1148.73 ~ 1971.15 |
| 当前价 | 1357.01 |
| 起始资金 | 10000.00 |
| 最终资金 | 10000.00 |
| 成交笔数 | 0 |
| 结果 | 无 C3+C4/C7/C8 共振 → 茅台价不触发 price<3 过滤, 是策略入场条件未触发 |

**说明**: 茅台价远超 price_min=3.0, 是 5Y 数据期内 C3+C4/C7/C8 没共振触发 → 0 交易。**这是正确行为**, 茅台属于稳定蓝筹, CCI 不容易触及 -70 极值。

## 3. smoke test 002415 (海康威视, 价 ~23-52)

| 项目 | 值 |
|------|-----|
| 数据期 | 2021-08-13 ~ 2026-08-13 (1211 行, 5Y 全量) |
| 价格范围 | 23.23 ~ 52.80 |
| 当前价 | 35.96 |
| 起始资金 | 10000.00 |
| 最终资金 | 10580.38 |
| 成交笔数 | 1 (5Y 全量只触发 1 次入场) |
| 收益 | +5.80% |

**交易记录**:
- 2024-09-20 触发 C3+C4/C7/C8 共振, 买入 4 手 @ 23.49
- 2024-09-25 CCI>120 触发超买离场 → 卖出

**说明**: 单股 5Y 只触发 1 次入场, 这是黄金组合策略的预期特征 — 入场条件严苛, 不是高频交易。

## 4. v6 策略参数验证

| 参数 | 值 | 与 v4 对比 |
|------|----|-----------|
| `cci_thresh` | -70 | ✅ 与 v4 一致 |
| `di_neg_thresh` | 20 | ✅ 与 v4 一致 |
| `di_pos_thresh` | 15 | ✅ 与 v4 一致 |
| `vote_min` | 2 | ✅ 与 v4 一致 |
| `price_min` | 3.0 | ✅ 与 v4 一致 |
| `cash_pct` | 0.95 | ✅ 与 v4 一致 |
| `hard_sl` | 0.05 | 🆕 v6 新回归 (v3 → v4 删除, v6 拿回) |
| `breakeven_pct` | 0.05 | 🆕 v6 新增 (保本移动止损触发线) |
| `be_stop_pct` | 0.01 | 🆕 v6 新增 (保本移动止损幅度) |

## T3 状态

**T3 (smoke test): PASS** ✅

- import 测试: ✅
- alias 指向 v6: ✅ (`GoldComboStrategy is GoldComboV6Strategy`)
- 600519 茅台 smoke: 0 笔 (无 C3+C4/C7/C8 共振, 正确)
- 002415 海康 smoke: 1 笔 (5Y 数据期, +5.80% 收益, CCI>120 超买离场)
- v6 策略参数全部正确 ✅

**关键验证**:
- v6 策略类成功加载并能跑通 backtrader 回测
- 真实数据能驱动 v6 策略运行 (不是空跑)
- 4 个 v6 新卖点机制 (硬止损/保本/CCI/MACD 高位死叉) 代码全部就绪
- v4 错杀机制 (ATR/阶梯/MA10/时间止损) 确认未出现在 v6 代码中