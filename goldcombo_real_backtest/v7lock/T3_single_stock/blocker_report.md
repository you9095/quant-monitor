# T3 · 单股验证 600438 通威股份 — BLOCKER (V7LOCK v2 OBV 不兼容)

## 执行结果

| 项目 | 值 |
|------|-----|
| **单股** | 600438 通威股份 (硅料龙头, 沪市主板) |
| **数据期** | 2022-01-01 ~ 2026-08-14 (2022 之后, 用户原话) |
| **bars 数** | 1107 |
| **价格范围** | 10.48 ~ 63.99 元 (远超 price_min=3.0 阈值) |
| **跑批结果** | ❌ V7LOCK 初始化失败 — `AttributeError: module 'backtrader.indicators' has no attribute 'OBV'` |
| **成交笔数** | **0** — 策略类在 `__init__` 阶段即崩溃, 永远到不了 buy/sell 决策 |
| **能否批量跑 T4** | ❌ **不能** — 单股 0 笔, blocker 触发 |

## 验证脚本输出

```
600438 通威股份 数据:
  bars 数: 1107
  价格范围: 10.48 ~ 63.99
  V7LOCK 初始化失败: module 'backtrader.indicators' has no attribute 'OBV'
  0 笔成交, 不能批量跑
```

## 根因复述 (与 T2 相同)

V7LOCK v2 用户原版策略代码 (line 37):
```python
self.obv = bt.ind.OBV()
```

backtrader 1.9.78.123 没有 OBV 指标 (`bt.ind.OBV` / `bt.ind.OnBalanceVolume` 都不存在)。

## 用户硬约束冲突

| 约束 | 状态 |
|------|------|
| ❌ 不准修改 V7LOCK v2 策略类任何一行 | 无法解决 OBV 缺失, 因不能改 |
| ❌ 不准加任何外部 hold/lock/sl 逻辑 | 不适用本 blocker |
| ❌ 不能 mock 数据 | 不适用本 blocker |

**结论**: V7LOCK v2 与当前 backtrader 版本 1.9.78.123 不兼容, 单股验证无法通过。

## 用户决策点 (与 T2 一致, 升级为 BLOCKER 上报)

主 agent 需要向用户上报, 由用户决策 (任一):

**选项 A**: 维持硬约束, V7LOCK v2 标 BLOCKER
- V7LOCK v2 文件 (commit 19f1cde) 一字不差保留
- T3/T4 跳过, 等用户决策
- **本任务 subagent #18 推荐此选项**, 因严格遵守"不得修改 V7LOCK"硬约束

**选项 B**: 升级 backtrader 到带 OBV 的版本
- backtrader 上游 OBV 实现需要从 mementum/backtrader contrib 获取
- 风险: 当前 Flask + V9 + 监控面板都依赖 backtrader 1.9.78.123

**选项 C**: 写 OBV 替代品子类化 V7LOCK
- 例: 把 OBV 替换为 WilliamsAD 或手动实现 OBV
- 显式违反"不准修改 V7LOCK v2 策略类任何一行"用户原话硬约束

**选项 D**: wrapper strategy 外部 monkey-patch
- 复杂, 违反"硬性规则全内嵌"精神

## 关键诚实声明

- V7LOCK v2 用户原版策略代码一字不差保留在 git commit `19f1cde`
- 不擅自 monkey-patch / 不擅自替换 OBV / 不擅自修改 V7LOCK 任何一行
- 不擅自改 backtrader 版本
- 不擅自跑 0 触发回测凑数 (那是 mock 性质, 违反 P0)
- 单股 0 笔 → 不批量跑, 这是用户原话"先单股验证能打出买入信号再批量跑"的反向: 单股都不能初始化, 谈何打出买入信号

## T4 状态

**SKIPPED** — T4 是 V7LOCK v2 1950 只沪深 A 股 5Y 真回测, 但 V7LOCK 策略类无法初始化, T4 跑不动, 不执行 (避免浪费 ~11 分钟跑批时间)。