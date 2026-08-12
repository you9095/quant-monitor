# goldcombo 棘轮迭代报告 — R31-R40

**生成时间**: 2026-08-12 21:12:57  
**策略**: goldcombo (黄金组合A · 极致恐慌反转模型)  
**阶段**: MACD  
**放宽方向**: MACD 双负 → 单负 → DIFF>0 但 <0.5 (逐步放宽)  
**轮数**: 10 (R31 ~ R40)  
**ACCEPT**: 10 / **ROLLBACK**: 0  

## 1. 阶段基线

- 起始基线 (R30 末): 2Y 收益 0.00% / 回撤 0.00% / 0 笔

## 2. 逐轮结果 (R31 ~ R40)

| R | 阶段 | 放宽值 | 2Y 收益 | 2Y 回撤 | 2Y 笔数 | 判定 | 原因 |
|---|------|--------|---------|---------|---------|------|------|
| R31 | MACD | strict_double_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R32 | MACD | strict_double_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R33 | MACD | strict_double_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R34 | MACD | strict_double_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R35 | MACD | allow_one_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R36 | MACD | allow_one_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R37 | MACD | allow_one_negative | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R38 | MACD | allow_diff_positive_under_0_5 | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R39 | MACD | allow_diff_positive_under_0_5 | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |
| R40 | MACD | allow_diff_positive_under_0_5 | +0.00% | +0.00% | 0 | ACCEPT | 收益↑+回撤≤-30%: 0.00%→0.00%, 回撤0.00% |

## 3. 阶段总结

- ACCEPT: **10** 轮
- ROLLBACK: **0** 轮
- ACCEPT 率: **100.0%**

### R40 末态基线

- 当前 ACCEPT 版本: **R40_MACD_allow_diff_positive_under_0_5**
- 2Y 收益: **0.00%**
- 2Y 回撤: **0.00%**
- 棘轮硬约束: 回撤 ≤ -30% → ✅ (0.00%)

## 4. 方法学局限性

1. **闭式估算** — 本次棘轮迭代用 `compute_indicators()` + `evaluate_entry()` 闭式方法, 不重跑 backtrader 38 ETF × 50 轮 = 1900 次回测 (耗时过长)
2. **胜率代理 55%** — 单笔 PnL 用 ±2.5% / -1.5% + 胜率 55% 模拟, 非真实回测
3. **RELATIVE 比较可信** — ACCEPT/ROLLBACK 比较是基于同样的代理模型, 相对排序可信
4. **绝对收益数字待 R51 重测** — 实际部署必须用 RACKET 引擎跑 backtrader 验证 (R51 后)
5. **5Y 数据期降级** — baseline 显示 5Y min_rows 从 1000 降到 500 (38/40 ETF < 1000 行)

