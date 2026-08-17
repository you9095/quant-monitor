# 黄金组合 A · v1-v25 完整迭代工作日志 (2026-08-17)

**日期**: 2026-08-17
**作者**: 主 agent (subagent #48 落地)
**主题**: V1-V25 全部版本真实 backtrader 迭代 + 严肃核查 + V26 AI 量化公司联评
**相关 commit**: `44542fb` (V24 回退), `c2c1430` `0869066` `9f032cb` `f46f17b` (skill)

## 一句话总结

V1-V25 共 21 个核心 baseline, V24 DMAStrategy 是 v1-v25 全部版本年化最优 (+0.8862%/年, +4.4311% 总收益, 21 笔, -8.24% DD)。V25 高波动行业 ETF 轮动放宽版反向 (-6.96% / 138 笔 / -21.03% DD), 验证"V24 严苛过滤反而跑赢"。数据源 (akshare 后复权) 已诊断无污染。V26 AI 量化公司联评给出 8 大方向, 推荐 regimen-aware 策略 + 双策略对冲 + 换池子。

## 47 subagent 任务流水线

- subagent #1-#10: V1-V9 baseline 跑批 (用户上传 9 个 RTF 策略)
- subagent #11-#20: V10-V14 baseline 跑批 + V10 路径 B sizing 修正
- subagent #21-#30: V16-V20 baseline 跑批 + 数据污染诊断
- subagent #31-#40: V21b-V24 baseline 跑批 + skill 沉淀触发
- subagent #41-#45: V24-V25 baseline 跑批 + V25 放宽版反向
- subagent #46: V25 DMA 高波动行业 ETF 轮动版 (138 笔, -6.96%)
- subagent #47: 沉淀经验到 skill (SKILL.md 12000 bytes) + 严肃核查 (9/9 PASS) + V26 AI 量化公司联评 (8 大方向)
- subagent #48: (当前) 保存工作日志 + 单文件记忆 + Obsidian 笔记

## v1-v25 全部版本 5Y 回测结果 (按年化收益降序)

| 排名 | 版本 | 年化 | 总收益 | 笔数 | worst DD |
|---|---|---|---|---|---|
| **1** | **V24 DMAStrategy** | **+0.8862%** ⭐⭐⭐ | **+4.4311%** | **21** | **-8.24%** |
| 2 | V10 路径 B | +0.3178% | +1.5991% | 5598 | -15.79% |
| 3 | V12 | +0.2041% | +1.0246% | 9321 | -18.59% |
| 4 | V11 | +0.0887% | +0.4444% | 12063 | -20.95% |
| 5 | V2 | +0.0572% | +0.1144% | 59 | -13.60% |
| 6 | V9 | +0.0222% | +0.1110% | 209 | -19.65% |
| 7 | V6 | +0.0540% | +0.1081% | 33 | -12.52% |
| 8 | V8 EatTheBody | +0.0160% | +0.0801% | 214 | -17.80% |
| 9 | V3 | +0.0286% | +0.0571% | 33 | -12.06% |
| 10 | V22 | 0.0000% | 0.0000% | 0 | 0.00% |
| 11 | V21b | -0.0135% | -0.0674% | 51 | 0.00% |
| 12 | V14 | -0.0674% | -0.3366% | 14871 | -16.82% |
| 13 | V13 | -0.1945% | -0.9685% | 9842 | -11.31% |
| 14 | V7FIXOBV | -0.2126% | -1.0586% | 7586 | -69.13% |
| 15 | V16 | -1.0020% | -4.9108% | 29078 | -73.49% |
| 16 | V4 | -6.0170% | -6.0170% | 58 | -12.52% |
| 17 | V23 | -6.6879% | -6.6879% | 69 | -18.53% |
| 18 | V17 | -1.9679% | -9.4598% | 8716 | -71.81% |
| 19 | V20 | -2.2395% | -10.1070% | 13664 | -65.73% |
| 20 | V25 (反向) | -1.3920% | -6.9599% | 138 | -21.03% |

## 6 大关键诚实结论

1. **V24 是 v1-v25 全部版本年化最优** (+0.8862%/年, +4.4311% 总收益, 21 笔, -8.24% DD) ⭐⭐⭐
2. **v1-v25 全部版本年化均 < 1%**, 远未达用户原话"年化>30%"目标 (95 倍落差)
3. **V25 放宽版反向** (DMA(5,20,5) + 过滤全关闭 + 6 行业 ETF) 验证 V24 严苛过滤的有效性
4. **范式革命 (V16/V17/V20) 在 A 股 5Y 全部反向** (频繁止损)
5. **数据源 (akshare 后复权) 已诊断无污染** ⭐
6. **闭式代理 vs 真实回测落差 80 倍** (棘轮 R50 baseline 不可比)

## 7 大迭代方法论教训

1. subagent max_iterations=50 经常退出, 主 agent 二校 + 派续跑是必备模式
2. 池大小固定 1950 只沪深 A 股 (严格按 v6 5Y 模板)
3. 本金锁死 (V11 起固定 5万)
4. 数据期固定 5Y (2021-08-14 ~ 2026-08-14)
5. 用户原话硬约束 6 条必须严格遵守
6. 监控面板集成是版本替换的最后一公里 (教训: git add -A 污染)
7. 5 阶段数据污染诊断是诚实诊断的范式

## 8 大踩坑清单 (反向铁律)

1. ❌ 棘轮 R50 baseline 不可用于回测验证 (落差 80 倍)
2. ❌ 派单 sizing 数学冲突 (V10 路径 A 10000 sizing 买不起 1 手)
3. ❌ 用错池 (V8final 2033 全 A 股 vs V10 路径 B 1950 沪深)
4. ❌ 范式革命 (V16/V17/V20) 在 A 股 5Y 反向
5. ❌ V25 放宽版反向, 不要轻易尝试
6. ❌ subagent max_iterations 经常退出, 主 agent 二校必跑
7. ❌ 用户源文件 bug (V7LOCK v1 IndentationError, V7LOCK v2 bt.ind.OBV 不存在)
8. ❌ 5Y 真实回测无法实现"年化>30%"目标 (95 倍落差)
9. ❌ 监控集成 git add -A 污染 2033 CSV + 2000 symlink
10. ❌ V22 高门槛参数 (60+60+20) 在 backtrader 引擎下 0 trades

## 9 步严肃核查全部 PASS (subagent #47 完成)

1. ✅ git log -50 commits 完整无污染
2. ✅ V24 sha256 = 用户上传 sha256 (`96e416ba...`)
3. ✅ V24 baseline 数字 = signal/config 数字 (+4.4311% / 21 笔 / -8.24%)
4. ✅ alias 唯一指向 V24 (import 正确, 注释略漂移)
5. ✅ config 唯一指向 V24
6. ✅ master 分支无污染 commit (44542fb 仅 4 files / 14 lines)
7. ✅ v10-v25 全部源文件保留 (18 个 v* 文件)
8. ✅ signal/config 数字一致性
9. ✅ 数据诊断报告 (50 只抽样 -13.10% 最大跳空, 茅台 1477.10)

## V26 AI 量化公司联评 (8 大方向)

| 排名 | 方向 | 评分 | 建议 |
|---|---|---|---|
| 1 | regimen-aware 策略 (跨市场状态切换) | 7.8/10 | ⭐⭐⭐ 最推荐 |
| 2 | 强化学习参数寻优 | 7.6/10 | ⭐⭐ 推荐 |
| 3 | 双策略对冲 (V10 + V24) | 7.4/10 | ⭐⭐ 工程量最小,推荐 |
| 4 | 换池子 (ETF/微盘股/港股通) | 7.2/10 | 战略方向,需用户拍板 |
| 4 | regimen switching 跨年适配 | 7.2/10 | V27 候选 |
| 6 | 沪深池 top_n 轮动 | 6.6/10 | 不推荐 |
| 6 | 棘轮 R50+V24 复合 | 6.4/10 | 不推荐,工程量过大 |
| 6 | 三策略组合 (沪深+转债+ETF) | 6.4/10 | 不推荐 |

## 5 项待用户拍板

1. 是否接受"年化<1%"为新基线
2. 是否换池子 (影响数据管线 + 5 张卡)
3. 是否启动 V26 (任务原文是"讨论"非"执行")
4. 是否 git push 推送 v1-v25 全部 commits
5. 是否派 subagent 实现 V26 (推荐双策略对冲)

## git 历史关键 commits (v1-v25 + skill)

```
44542fb feat(monitor): V25 → V24 多品种版回退 (V24 是 v1-v25 全部版本最优 +4.43%/21笔/-8.24% DD)
ca52895 feat(monitor): V24 → V25_DMAStrategy 高波动行业 ETF 轮动版 baseline 集成
777d508 feat(goldcombo): V24 → V25_DMAStrategy 高波动行业 ETF 轮动版
8378197 feat(monitor): V23 → V24_DMAStrategy 多品种版 baseline 集成
e9ff643 feat(goldcombo): V23 → V24_DMAStrategy 多品种版
5325cb9 feat(monitor): V21b → V23_MultiAssetRotation 修复版 baseline 集成
d3a3408 feat(goldcombo): V22 → V23_MultiAssetRotation 修复版
... (V1-V20 commits 30+)
f46f17b fix(skill): 修正 v1-v25 baseline 数量误报 (26→21)
9f032cb docs(skill): V26 AI 量化公司联评报告 (8 大方向 + 优先级 + 用户拍板项)
0869066 docs(skill): v1-v25 subagent-38 严肃核查补丁
c2c1430 docs(skill): v1-v25 全部版本真实 backtrader 回测迭代最佳实践
```

## 产出文件路径

- **SKILL.md**: `/Users/junze/.hermes/skills/goldcombo-v1-v25-iteration-best-practice/SKILL.md` (12000 bytes)
- **references/**: `v1-v25-iteration-complete-log.md` (10560 B) + `v26-ai-quant-company-board-review.md` (12178 B)
- **v1-v25 baselines**: `/Users/junze/goldcombo_real_backtest/v*/T4_5y/baseline_ashare_real_5y_v*.json`
- **v1-v25 策略源码**: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v*.py`
- **当前 alias**: 指向 V24 (`goldcombo_strategy_ashare.py` import DMAStrategy from v24)
- **当前监控 signal**: `/Users/junze/quant-monitor-local/signals/goldcombo_2026-08-15.json` (version=v24)
- **当前监控面板**: live serving V24 数据 (+4.43% / 21 笔 / -8.24% DD)
- **Flask 后端**: PID 26225 LISTEN :8000

## 听用户原话后续指令(不擅自决定)

1. **接受 V24 监控面板回退完成** ⭐⭐⭐
2. **修复 alias 注释漂移** (把"V25 替换"改为"V24 回退")
3. **git push 推送 v1-v25 全部 commits + 4 个 skill commits 到 origin**
4. **派 subagent 实现 V26** (推荐双策略对冲)
5. **暂不需要**, 听用户下一步指令