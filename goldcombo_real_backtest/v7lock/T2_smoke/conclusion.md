# T2 · smoke test — FAIL (V7LOCK v2 用户原版策略代码与 backtrader 1.9.78.123 不兼容)

## 执行结果

| 项目 | 值 |
|------|-----|
| **import 测试** | ✅ import 成功 (类名 `GoldComboV7_Locked`) |
| **5 参数验证** | ✅ `vote_min=3, price_min=3.0, cash_pct=0.95, hard_sl=0.08, trail_sl=0.15` |
| **600519 茅台 跑批** | ❌ FAIL — `AttributeError: module 'backtrader.indicators' has no attribute 'OBV'` |
| **002415 海康 跑批** | ❌ FAIL — 同上 (V7LOCK 策略类初始化即失败) |

## 关键诊断: V7LOCK v2 用户原版代码与 backtrader 1.9.78.123 不兼容

### 错误堆栈
```
File "/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v7lock.py", line 37, in __init__
    self.obv = bt.ind.OBV()
               ^^^^^^^^^^
AttributeError: module 'backtrader.indicators' has no attribute 'OBV'
```

### 根因分析

V7LOCK v2 用户原版代码 (`goldcombo_strategy_ashare_v7lock.py` line 37) 使用了 `bt.ind.OBV()` 指标:

```python
self.macd = bt.ind.MACD(period_me1=12, period_me2=26, period_signal=9)
self.cci = bt.ind.CCI(period=14)
self.plus_di = bt.ind.PlusDI(period=14)
self.minus_di = bt.ind.MinusDI(period=14)
self.adx = bt.ind.ADX(period=14)
self.trix = bt.ind.TRIX(period=12)
self.trma = bt.ind.SMA(self.trix, period=9)
self.obv = bt.ind.OBV()                              # ← 不存在
self.maobv = bt.ind.SMA(self.obv, period=30)
```

但 backtrader 1.9.78.123 (当前安装版本) **没有任何 OBV 实现**:
- `bt.ind.OBV` ❌ 不存在
- `bt.ind.OnBalanceVolume` ❌ 不存在
- `/backtrader/indicators/contrib/` 只有 `vortex.py`, 无 OBV
- 整个 backtrader 1.9.78.123 安装内 `find ... -name "obv.py"` 找不到任何 OBV 文件

### 用户硬约束冲突

| 约束 | 状态 |
|------|------|
| ❌ **不准修改 V7LOCK v2 策略类任何一行** | 用户原话"不得更改", 硬性规则全内嵌 |

**冲突**: 不修改 V7LOCK v2 → 跑不动; 修改 V7LOCK v2 替换 OBV → 违反用户原话硬约束。

### V7LOCK 5 强势信号中 OBV 的角色

OBV 是 5 强势信号之一:
1. DMI 多方: +DI>30, -DI<20, ADX>32
2. MACD 水上: DIFF>DEA 且 DIFF>0 且 DEA>0
3. **TRIX 零上: TRIX>TRMA 且 TRIX>0**  ← backtrader 有
4. **OBV 强势: OBV > MAOBV**  ← backtrader 没有 OBV
5. CCI 强势: CCI>120

### 已知 V7LOCK v1 (subagent #17) 也是同样的 OBV 错误

V7LOCK v1 在 subagent #17 落盘时是 `else: #` 处截断 (IndentationError)。该 v1 也没机会跑到 OBV 那里。但完整 v2 解开 RTF 后才暴露 OBV 不存在的问题。

## 用户决策点 (主 agent 上报)

V7LOCK v2 用户原版代码 + 当前 backtrader 版本 = **根本性不兼容**。

主 agent 需要选择 (任一):

**选项 A**: 维持硬约束, V7LOCK v2 标 BLOCKER, 不跑 T3/T4
- V7LOCK v2 用户原版一字不差保留在 git commit 19f1cde
- T3/T4 直接 blocker 落档, 不批量跑
- 主 agent 上报用户: "V7LOCK v2 与 backtrader 1.9.78.123 OBV 指标缺失不兼容, 需要用户决策"

**选项 B**: 升级 backtrader (风险大, 改环境)
- backtrader 上游有 OBV 实现 (github.com/mementum/backtrader, 但这是非官方 fork)
- 当前已部署的 Flask + 监控面板 + V9 等都依赖此 backtrader 版本, 升级风险大

**选项 C**: 子类化 V7LOCK 加 OBV 替代品 (违反"不得修改 V7LOCK 策略类任何一行")
- 例如把 OBV 替换为 WilliamsAD (`bt.ind.WilliamsAD` 存在, 但属于 V7LOCK v2 用户原版的修改)
- 显式违反用户原话硬约束

**选项 D**: 写 wrapper strategy, 调用 V7LOCK 但外部 monkey-patch OBV 缺失
- 复杂, 违反"不准加任何外部 hold/lock/sl 逻辑"精神
- 子类化也属于修改策略类

**推荐**: 选项 A (维持硬约束, blocker 上报)

## 产出

- 本文件: T2 blocker 报告
- V7LOCK v2 策略文件 (commit 19f1cde) 保留一字不差
- 不擅自 monkey-patch / 不擅自替换 OBV / 不擅自修改 V7LOCK 任何一行

## 备查

### 600519 茅台 跑批 (失败, OBV 不存在)
```
File "/Users/junze/.../goldcombo_strategy_ashare_v7lock.py", line 37, in __init__
    self.obv = bt.ind.OBV()
               ^^^^^^^^^^
AttributeError: module 'backtrader.indicators' has no attribute 'OBV'
```

### 002415 海康 跑批
同样会失败 (同样的 V7LOCK 策略类), 未运行 (节省时间)。

### V7LOCK 文件状态 (commit 19f1cde)
- 98 行, sha256 `85f42b63e7c3131c28dd24db4b017744e0decab1ca6f31b033c80bc0048fd9dd`
- 一字不差, 与 RTF 解出文件完全一致
- git 历史完整保留 (v1-v9: c514fdd / 67a5f98 / 413a4b2 / 6d29242)

## 结论

T2 FAIL (V7LOCK v2 用户原版 OBV 不兼容 backtrader 1.9.78.123)。
T3 (单股验证 600438) 跳过 — V7LOCK 初始化即失败, 无法验证。
T4 (1950 只 5Y 真回测) 跳过 — 阻塞, 必须先解决 OBV 问题。

主 agent 需要向用户上报 OBV blocker, 由用户决策:
- 选项 A: 维持硬约束, 标 BLOCKER, 等待用户决策
- 选项 B/C/D: 改 backtrader 升级 / 子类化 / monkey-patch (任一都违反用户原话硬约束)

**所有改动均不动 V7LOCK v2 用户原版策略类** (commit 19f1cde 已一字不差保留)。