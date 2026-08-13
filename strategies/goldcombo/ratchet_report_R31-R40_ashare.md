# goldcombo 棘轮迭代报告 — R31-R40

**生成时间**: 2026-08-13 12:22:42  
**策略**: goldcombo (黄金组合A · 沪深 A 股池)  
**阶段**: MACD  
**放宽方向**: MACD 双负 → 单负 → DIFF>0 但 <0.5 (逐步放宽)  
**轮数**: 10 (R31 ~ R40)  
**ACCEPT**: 0 / **ROLLBACK**: 10  

## 1. 阶段基线

- 起始基线 (R30 末): 2Y 收益 6.50% / 回撤 -2.98% / 9 笔

## 2. 逐轮结果 (R31 ~ R40)

| R | 阶段 | 放宽值 | 2Y 收益 | 2Y 回撤 | 2Y 笔数 | 判定 | 原因 |
|---|------|--------|---------|---------|---------|------|------|
| R31 | MACD | strict_double_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R32 | MACD | strict_double_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R33 | MACD | strict_double_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R34 | MACD | strict_double_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R35 | MACD | allow_one_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R36 | MACD | allow_one_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R37 | MACD | allow_one_negative | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R38 | MACD | allow_diff_positive_under_0_5 | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R39 | MACD | allow_diff_positive_under_0_5 | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |
| R40 | MACD | allow_diff_positive_under_0_5 | +3.4866% | -1.50% | 3 | ROLLBACK | 2Y 收益 3.49% < 基线 14.23% OR 回撤 -1.50% < -30% → ROLLBACK |

## 3. 阶段总结

- ACCEPT: **0** 轮
- ROLLBACK: **10** 轮
- ACCEPT 率: **0.0%**

### R40 末态基线

- 当前 ACCEPT 版本: **R20_DMI_20** (R31-R40 全部 ROLLBACK, 基线不变)
- 2Y 收益: **3.4866%**
- 2Y 回撤: **-1.50%**
- 棘轮硬约束: 回撤 ≤ -30% → ✅ (-1.50%)

### 棘轮最终基线 (R20_DMI_20, 全局 cross-report 一致性声明)

> subagent #D 2026-08-13 数字一致性铁律更正 — 本报告 (R31-R40) 阶段全部 ROLLBACK, 末态基线仍指 **R20_DMI_20**。
> 派单与 subagent #B 报告将 5Y 数字误标为 14.23% 是错的, **真值 5Y = 0.2557%** (来源 ratchet_final_baseline_ashare.json)。
>
> | 数据期 | 收益 | 回撤 | Sharpe | 笔数 |
> |--------|------|------|--------|------|
> | 2Y (主) | **14.2298%** | -1.50% | 20.25 | 7 |
> | 5Y (副) | **0.2557%** | -5.4849% | 0.3014 | 13 |

## 4. 方法学局限性

1. **闭式估算代理** — 本次棘轮迭代用 `compute_indicators()` + `evaluate_entry()` + 等权汇总, 单笔 PnL ±2.5%/-1.5% + 胜率 55% 代理 (非真实 backtrader 回测)
2. **池采样 (top 300)** — 沪深 A 股池总 2002 (2Y) / 1934 (5Y), 棘轮评估按流动性降序取前 300 只作代表性样本 (与 ETF 池 38 只等比缩放)
3. **RELATIVE 比较可信** — ACCEPT/ROLLBACK 比较基于同样的代理模型, 相对排序可信
4. **绝对收益数字待 R51 重测** — 实际部署必须用 backtrader 在完整 2002 池上重测 (R51 后)
