# T3 — V14_ScaleIn smoke test 验证

**状态**: ✅ PASS

## 验证结果

| 验证项 | 期望 | 实际 | 结果 |
|--------|------|------|------|
| 类名 | `GoldComboV14_ScaleIn` | `GoldComboV14_ScaleIn` | ✅ |
| 父类 | `(bt.Strategy,)` | `(bt.Strategy,)` | ✅ |
| cci_thresh=-70.0 | ✓ | ✓ | ✅ |
| di_neg_thresh=20.0 | ✓ | ✓ | ✅ |
| di_pos_thresh=15.0 | ✓ | ✓ | ✅ |
| vote_min=1 | ✓ | ✓ | ✅ |
| price_min=3.0 | ✓ | ✓ | ✅ |
| half_pct=0.10 | ✓ | ✓ | ✅ |
| hard_sl=0.20 | ✓ | ✓ | ✅ |
| trail_sl=0.25 | ✓ | ✓ | ✅ |
| `self.added = False` in init | ✓ | ✓ | ✅ |
| `self.added = True` in next | ✓ | ✓ | ✅ |
| `self.added=False` reset in close | ✓ | ✓ | ✅ |
| `if not self.added` 加仓判定 | ✓ | ✓ | ✅ |
| 002415 海康 2022-2026 跑得出 | 不报错 | 收益 +1.26% | ✅ |
| 5万本金 lock | setcash(50000.0) | 50000.00 → 50630.23 | ✅ |

## 002415 海康 (V14 设计特性)

- 起始: 50000.00
- 最终: 50630.23
- 总收益: **+1.26%**

## 硬约束遵守

- ✅ V14 能 import
- ✅ 8 参数 (7 核心 + vote_min) 全部正确
- ✅ self.added 状态机源码验证通过 (init/next/close 三处)
- ✅ V14 一字不差, 未加任何外部 hold/lock
