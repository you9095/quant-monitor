# T3 · smoke test (V13 import + 4 参数 + MyOBV 可用)

**Status**: PASS

## T3.1 import + 4 参数验证

```
import OK: GoldComboV13_PureRight / MyOBV
4 params:
  price_min = 3.0
  per_pos_pct = 0.1
  hard_sl = 0.15
  trail_sl = 0.25
```

✅ V13 类能 import
✅ MyOBV 自定义类能用 (修复 OBV bug)
✅ 4 参数与用户原版一致 (无修改)

## T3.2 smoke test 002415 海康 (价 ~30.89)

```
002415 海康 数据行数: 1117, 区间: 2022-01-04 ~ 2026-08-13, 均价: 30.89
起始: 50000.00
最终: 49247.61
总收益: -1.5048%
trade list items: 1
```

✅ 002415 海康也跑出 1 笔 closed trade (V13 在高价股也能触发)
✅ 总收益 -1.5048% (轻微亏损 — 1 笔交易触发了 15% 硬止损或 MACD 死叉)
✅ 强制 setcash(50000.0) 锁死

## 结论

V13 在 600438 (中等价 40) 和 002415 (高价 30) 都能触发, 表明 5 个原始卖点条件在 5Y 内可满足。继续 T4 全池 5Y 跑批。
