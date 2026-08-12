# goldcombo · 黄金组合A:极致恐慌反转模型

> **M01 集成阶段 (2026-08-12)**: 本目录创建于 quant-monitor-local 第 6 策略卡集成阶段。占位信号已落 `signals/goldcombo_2026-08-12.json`,2Y/5Y 回测将由 cron 8/13 01:30 启动后真正跑出。

## 策略说明

- **strategy_id**: `goldcombo` (固定,与现有 5 策略并存,作为第 6 张策略卡)
- **中文名**: 黄金组合A
- **描述**: 极致恐慌反转模型
- **颜色**: `#ef4444` (红)
- **初始资金**: 10000
- **当前版本**: `R0_initial` (M01 集成阶段占位)

## 核心逻辑(从 RTF 提取的真代码,backtrader 框架)

数据源: 用户附件 `~/Downloads/股票筛选项目/自己写量化策略和脚本/GoldComboStrategy-2.py` (RTF 包裹, 已由 `run_goldcombo_backtest.py` 解出)

**指标** (4 个 + 1 triplet):
- MACD (12/26/9) — 周期金叉
- BOLL (20, 2σ) — 开口放大
- CCI (14) — 极端超卖
- DMI (14) — +DI / -DI 极化
- TRIX (12) + TRMA (SMA 9) — 趋势确认

**入场条件** (4 同时满足):
- **C3**: MACD 低位金叉 + MACD 双负 (`macd > signal` 且 `macd[-1] <= signal[-1]` 且 `macd < 0` 且 `signal < 0`)
- **C4**: BOLL 开口放大 (`bw = top-bot; bw > bw_prev`)
- **C7**: CCI < -100 (恐慌超卖)
- **C8**: +DI < 10 且 -DI > 30 (空方极化)

**出场条件** (任一满足):
- **S2**: CCI > 120
- **S3**: +DI > 30 且 -DI < 20 且 ADX > 32
- **S4**: TRIX > TRMA 且 TRIX > 0
- **S6**: MACD > signal 且 MACD 双正

**止损**: `sl_pct = 0.08` (8% 硬止损, 立即平仓)

## 文件清单

| 文件 | 角色 | 何时写入 |
|---|---|---|
| `README.md` | 策略说明 + 指标/入场/出场/止损定义 | 2026-08-12 M01 集成 |
| `run_backtest.py` | 独立运行 backtrader 回测的入口 (stub, 真实数据由 cron 8/13 启动后获取) | 2026-08-12 M01 集成 |
| `signal_template.json` | 信号文件 schema 模板 (空数据, 占位) | 2026-08-12 M01 集成 |

## 关联文件

- 根目录占位: `signals/goldcombo_2026-08-12.json`
- 集成入口: `scripts/run_goldcombo_backtest.py` (从 RTF 解出真 Python 代码)
- 配置: `config/strategies.json` 末段 `goldcombo` 条目
- 监控面板: `index.html` 第 6 张策略卡 (CSS 变量 `--goldcombo-start/end` + `.goldcombo` 类)

## 待办 (cron 8/13 01:30 启动后)

- [ ] 2Y 数据回测 (2024-08-12 ~ 2026-08-12)
- [ ] 5Y 数据回测 (2021-08-12 ~ 2026-08-12)
- [ ] 棘轮 50 轮迭代 (cron 8/13 02:30 启动, 每 10 轮备份 + 报告)
- [ ] 信号文件每日刷新 (`signals/goldcombo_YYYY-MM-DD.json`)
- [ ] 升级策略版本从 `R0_initial` → `R1_xxx`
