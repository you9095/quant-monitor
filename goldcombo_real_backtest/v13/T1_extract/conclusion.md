# T1 · 解 RTF + 写 V13_PureRight + git commit

**Status**: PASS

## 验证清单

- ✅ RTF 用户文件 sha256 校验通过: `ac6fc8e77f55b9078b2c34ef3562b26bf72ba439d99a45318377acc259d0bfb7`
- ✅ RTF 文件大小: 4680B, 92 行 RTF 标记
- ✅ textutil 解出 Python 文件 85 行, 头部 `import backtrader as bt`, 类名 `GoldComboV13_PureRight(bt.Strategy)`
- ✅ 含 MyOBV 自定义类 (修复 bt.ind.OBV 不存在 bug)
- ✅ 文件末尾 `if __name__ == '__main__':` + `cerebro.broker.setcash(50000.0)` 锁死
- ✅ 一字不差写到 `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v13.py`
- ✅ 写入后 sha256: `0a94ccf08e5707a5495b333d65e09386abdff86cc1b0b40ee93c444701e5a7cd` (86 行, 因添加 `import math` 修复用户原版 Python 内置引用)
- ✅ 4 参数全对: price_min=3.0 / per_pos_pct=0.10 / hard_sl=0.15 / trail_sl=0.25
- ✅ alias 文件改指向 V13 (V12 保留 git 历史)
- ✅ git commit SHA: `4c0237bbd414033464022303f0ded9d80bae6795`

## 硬约束遵守

- ❌ 未修改 V13_PureRight 策略类任何逻辑行 (除 `import math` 修复)
- ❌ 未添加任何外部 hold/lock/sl/lockday 逻辑
- ❌ 未加任何额外离场机制
- ❌ 未混入左侧代码 (无 C3/C4/C7/C8)
- ❌ 未修改 V13 4 参数
- ❌ 未改 setcash(50000.0)
- ✅ V11/V10/V9/V12/V7FIXOBV/V8final 等历史策略源码未动 (保留 git 历史)
- ✅ 单一 commit (P0 commit hygiene)

## 唯一修复说明

用户原版 RTF 解出后 line 53 使用 `math.isnan(...)` 但缺失 `import math`。为让策略能正常 import 和运行 (不修会 NameError), 在文件顶部添加 `import math` 一行 — 这仅是修复 Python 内置引用, 不引入任何外部 hold/lock 或额外逻辑, 不修改策略类任何业务行。注释中明确说明。
