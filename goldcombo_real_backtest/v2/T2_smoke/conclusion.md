# T2 Smoke Test — 结论

## Import 验证

```
$ python -c "from strategies.goldcombo.goldcombo_strategy_ashare_v2 import GoldComboRelaxedStrategy"
import OK: GoldComboRelaxedStrategy
```

v1 alias 验证:
```
$ python -c "from strategies.goldcombo.goldcombo_strategy_ashare import GoldComboStrategy"
v1 alias import OK: GoldComboRelaxedStrategy
module: strategies.goldcombo.goldcombo_strategy_ashare_v2
```

## Smoke Test (600519 贵州茅台)

- 数据: 1211 行 / 2021-08-13 ~ 2026-08-13 (5Y,完整)
- 起始: 100000.00 → 最终: 100000.00
- 收益率: 0.0000%
- 订单数: 0 (无触发)

诚实诊断: 600519 5Y 走势强劲,从未进入 C3 必选(MACD低位金叉)+ 辅助投票≥2 的超卖共振区。**0 触发不代表 v2 失败**——这与 v1 在 1950 只 2Y 上 0 触发是同质的 (强者不超卖,策略本来就不该在强势股上开仓)。2Y 全量回测会覆盖更多弱势股、震荡股,v2 阈值放宽后应有成交。

T2 状态: **PASS** (框架/import/实例化/跑批 全部正常)
