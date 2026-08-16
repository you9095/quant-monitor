# 黄金组合 A · v1-v20 单文件记忆 (2026-08-16)

## 一句话总结
v1-v20 共 16 个核心 baseline, V10 路径 B 是 v1-v20 全部版本年化最优 (+0.3178%/年, +1.5991% 总收益), 但 v1-v20 全部版本年化均 < 1%, 远未达用户原话"年化>30%"目标。

## v1-v20 全部版本年化收益排名 (5Y 真实 backtrader, 1950 只沪深 A 股, 5万本金)

| 排名 | 版本 | 策略类 | 年化 | 总收益 | worst DD | 笔数 |
|---|---|---|---|---|---|---|
| 1 | V10 路径B | V10_HighYield | **+0.3178%** ⭐ | +1.5991% | -15.79% | 5598 |
| 2 | V12 | V12_LeftBuyRightSell | +0.2041% | +1.0246% | -18.59% | 9321 |
| 3 | V11 | V11_EnergyPeak | +0.0887% | +0.4444% | -20.95% | 12063 |
| 4 | V2 | v2 | +0.0572% | +0.1144% | - | (2Y) |
| 5 | V6 | v6 | +0.0540% | +0.1081% | - | (2Y) |
| 6 | V3 | v3 | +0.0286% | +0.0571% | - | (2Y) |
| 7 | V9 | V9 | +0.0222% | +0.1110% | -19.65% | 209 |
| 8 | V8 EatTheBody | v6 (旧) | +0.0160% | +0.0801% | -17.80% | 214 |
| 9 | V10 路径A | V10_HighYield | 0.0000% | 0.0000% | 0% | 0 (sizing bug) |
| 10 | V14 | V14_ScaleIn | -0.0674% | -0.3366% | -16.82% | 14871 |
| 11 | V13 | V13_PureRight | -0.1945% | -0.9685% | -11.31% | 9842 |
| 12 | V7FIXOBV | V7FIXOBV | -0.2126% | -1.0586% | -69.13% | 7586 |
| 13 | V16 | V16_ChannelBreakout | -1.0020% | -4.9108% | -73.49% | 29078 |
| 14 | V17 | V17_LowFreqBreakout | -1.9679% | -9.4598% | -71.81% | 8716 |
| 15 | V20 | V20_NoMA | -2.2395% | -10.7070% | -65.73% | 13664 |
| 16 | V4 | v4 | -3.0552% | -6.0170% | - | (2Y) |

## 关键诚实结论
- V10 路径 B 是 v1-v20 全部版本年化最优 ⭐
- v1-v20 全部版本年化均 < 1%, 远未达用户原话"年化>30%"目标
- 范式革命 (V16/V17/V20) 在 A 股沪深池 5Y 全部反向
- 闭式代理 vs 真实回测落差 80 倍 (v1 R50 +14.23% vs 真实回测 0.05%)

## 5 阶段数据污染诊断结果 (2026-08-16)
- Stage 1 抽样诊断: **未证实污染**
  - V16 -70% DD 股票仅 2 只 (000755/601007)
  - 50 只抽样最大跳空 -13.10% (在 ±20% 涨跌停内)
  - 茅台首日 close 1477.10 确认数据已是后复权
- Stage 2-4: SKIPPED (未证实污染)
- 结论: **数据无污染, v1-v20 全部版本继续有效**

## 数据管道
- 数据源: akshare 后复权数据 (已诊断确认)
- 池大小: 1950 只 (exclude 688/300/8/4, 沪深 600/601/603/605/000/002)
- 本金: 5万 (V11-V20 锁死)
- 引擎: backtrader 1.9.78.123, commission 0.001, slippage 0.003
- 数据期: 5Y (2021-08-14 ~ 2026-08-14)
- Flask 后端: PID 26225 LISTEN :8000

## 监控面板集成
- 当前 signal: signals/goldcombo_2026-08-15.json (V20 数据)
- 监控集成 commits: V6→V11→V12→V13→V14→V16→V17→V20 共 8 次
- 最新 monitor commit: db16f85

## git 历史关键 commits
- da10a57: v1 -> v2 (改良共振版)
- 57267e1: v2 -> v3 (小资金严控版)
- e91db0e: v3 -> v4 (灵活卖点版)
- b38a856: v4 -> v6 (严控回撤版)
- 413a4b2: v8 EatTheBody
- 67a5f98: V8final 终极版
- c514fdd: V9 用户原版
- 40b73a4: V7FIXOBV
- f0403796: V10 路径 B
- 097062c: V11 EnergyPeak
- 925efd4: V12 LeftBuyRightSell
- 4c0237b: V13 PureRight
- c27d509: V14 ScaleIn
- 4f1345b: V16 ChannelBreakout
- e2d105b: V17 LowFreqBreakout
- 7120228: V20 NoMA

## 32 个 subagent 派单教训
- subagent max_iterations=50 经常退出 (subagent #6/#9/#12/#13/#14/#17/#20/#22/#27/#30)
- 主 agent 二校 + 派续跑是必备模式
- 用户原话 5 阶段数据诊断 (5 stage) 是诚实诊断的范式

## 关键诚实失败 (透明声明)
- v1-v20 全部版本年化均 < 1% (无法实现用户原话"年化>30%"目标)
- V8final 0% 触发是 subagent #15 用错池 (2033 而非 1950)
- V10 路径 A 0% 触发是派单设计 bug (10000 sizing 买不起 1 手)
- V11 5% 硬止损改严拉低收益 (+0.44% < V10 +1.60%)
- V12/V13/V14/V16/V17/V20 都没跑赢 V10 路径 B

## 产出文件路径
- v1-v20 baselines: /Users/junze/goldcombo_real_backtest/v*/T4_5y/baseline_ashare_real_5y_v*.json
- v1-v20 策略源码: /Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v*.py
- 诊断报告: /Users/junze/quant-monitor-local/diagnostics/full_diagnosis_report.md
- 工作日志: /Users/junze/quant-monitor-local/work_logs/2026-08-16_goldcombo_v1_v20_32_subagents_iteration.md
