# T2 · git commit 单一 commit — 结论

**执行时间**: 2026-08-14 23:02
**任务**: v3 → v4 替换 git 提交(单 commit,全部改动)
**状态**: PASS

## commit 信息

```
commit e91db0e243bf3a0fe46ca063d3c23d99e3db69d2
Author: subagent <subagent@local>
Date:   Fri Aug 14 23:02:26 2026 +0800

    feat(goldcombo): v3 → v4 灵活卖点版 (ATR 自适应止损 + 阶梯移动止盈 + 时间止损)

    v3 (小资金严控) 1950 只 2Y 跑出 33 笔成交 + 0.057% 收益, 但 5% 硬止损 + 8% 固定移动止盈对震荡市过严。
    v4 用户手动优化方案:
    - 硬止损 5% → ATR 自适应 (entry - ATR*2.5, 波动率自动调整)
    - 移动止盈 固定 8% → 阶梯式 (盈利>20% trail=10%, >10% trail=8%, >0% trail=6%)
    - 新增 MA10 均线离场 (盈利>3% 且跌破 MA10)
    - 新增 时间止损 (持仓 20 天 + 盈利<3% 强制平仓)
    - 去掉 MACD 高位死叉离场
    - C7 CCI 阈值 <-80 → <-70 (更敏感)
    - C8 -DI 阈值 >25 → >20 (更敏感)
    - 滑点 0.001 → 0.003 (3 倍, 更保守)
    - price_min 保持 3.0

    v4 类名: GoldComboV5Strategy (用户命名混乱, 文件名第四版, 类名 v5)
    v3 文件保留为 goldcombo_strategy_ashare_v3.py (已备份)
    v4 新文件: goldcombo_strategy_ashare_v4.py
    alias 文件 goldcombo_strategy_ashare.py 改 import 指向 v4

    来源: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第四版V5.py
    sha256: 03162c80dc0ff1a0aff4eb9d5bd089f206cd3ad0e03b0dab51dd3a9fe876acde

    v1 + v2 + v3 备份链:
    - v1 备份: ~/goldcombo_real_backtest/v1_backup/
    - v2 备份: ~/goldcombo_real_backtest/v2_backup/
    - v3 备份: ~/goldcombo_real_backtest/v3_backup/ (本次新建)

    数据层过滤: 用户原话要求 price<2 元股剔除, 在 run_backtest 阶段按 first_price<2 过滤股票池 (不污染策略类 price_min)。
```

**commit SHA**: `e91db0e243bf3a0fe46ca063d3c23d99e3db69d2`
**short SHA**: `e91db0e`

## commit 包含文件清单

```
2 files changed, 165 insertions(+), 6 deletions(-)
 create mode 100644 strategies/goldcombo/goldcombo_strategy_ashare_v4.py
 M strategies/goldcombo/goldcombo_strategy_ashare.py
```

| 文件 | 改动 | 来源 |
|------|------|------|
| `strategies/goldcombo/goldcombo_strategy_ashare_v4.py` | 新增 (6744 B) | RTF 解码 + 用户上传源 (sha256 03162c80...) |
| `strategies/goldcombo/goldcombo_strategy_ashare.py` | 修改 (alias 改 import v3→v4) | alias 兼容层 |

未碰的文件(承诺 P0 不污染):
- `goldcombo_strategy.py` (ETF 池版)
- `goldcombo_strategy_ashare_v3.py` (v3 保留)
- `goldcombo_strategy_ashare_v2.py` (v2 保留,如存在)
- `ratchet_*.json` (棘轮基线)
- `ratchet_*_ashare.py` (棘轮脚本)
- `monitor_*.html` 等前端文件

## 工作树状态(commit 后)

针对我们的 2 个文件:
```
(empty)  ← working tree 干净
```

未追踪但已存在的 WIP 文件(预先存在,subagent 未触碰):
- `strategies/goldcombo/_ratchet_fast_runner.py`
- `strategies/goldcombo/_rebaseline_entry.py`
- `strategies/goldcombo/goldcombo_ratchet_ashare.py`
- `strategies/goldcombo/ratchet_backup_R*.json`
- `strategies/goldcombo/ratchet_baseline_ashare.json`
- `strategies/goldcombo/ratchet_final_baseline_ashare.json`
- `strategies/goldcombo/ratchet_log_ashare.json`

这些属于其他任务的 WIP,本次任务 commit 不涉及。

## git 历史(最新 4 次)

```
e91db0e feat(goldcombo): v3 → v4 灵活卖点版 (ATR 自适应止损 + 阶梯移动止盈 + 时间止损)  ← 本次
57267e1 feat(goldcombo): v2 → v3 小资金严控版 (5% 硬止损 + 8% 移动止盈 + 价格过滤)
da10a57 feat(goldcombo): v1 → v2 改良共振版 (Gated Voting C3+vote≥2)
4964e52 feat(ashare): 重启 A 股 K 线下载 + 修复 pool + 重写 signals/goldcombo_2026-08-13.json
```

## 下一步

T3 · smoke test (import + 单股验证)