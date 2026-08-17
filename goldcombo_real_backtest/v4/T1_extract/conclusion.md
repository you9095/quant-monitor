# T1 · 解 RTF + 写 v4 策略文件 — 结论

**执行时间**: 2026-08-14 23:00
**任务**: 解 RTF 包裹的 Python 源 → 写 v4 策略文件 + 改 alias
**状态**: PASS

## v4 用户上传文件校验

```
路径:    /Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第四版V5.py
大小:    6609 字节
sha256:  03162c80dc0ff1a0aff4eb9d5bd089f206cd3ad0e03b0dab51dd3a9fe876acde
头部:    {\rtf1\ansi\ansicpg936\cocoartf2709   ← RTF 包裹确认
```

## RTF 解码方法

**方法**: macOS native `textutil -convert txt` (备选 re.sub,未用上)
**命令**:
```bash
cd /Users/junze/goldcombo_real_backtest/v4/T1_extract
textutil -convert txt -inputencoding UTF-8 -encoding UTF-8 \
  -output goldcombo_strategy_v4_clean.txt \
  "/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第四版V5.py"
```

**解码验证**:
- 行数: 114 行 (源 121 行,RTF 解压后 114 行有效 Python)
- 头部: `import backtrader as bt` ✓ 在第 1 行
- 类名: `class GoldComboV5Strategy(bt.Strategy):` ✓ 用户命名 v5
- AST 解析: OK (`python3 -c "import ast; ast.parse(...)"` 通过)
- 卖点灵活参数全部在: `atr_period=14`, `atr_multiplier=2.5`, `ma_exit_period=10`, `max_hold=20`
- 买点参数: `cci_thresh=-70`, `di_neg_thresh=20`, `di_pos_thresh=15`, `vote_min=2`, `price_min=3.0`

## v4 文件落项目位置 + sha256

| 文件 | sha256 | 大小 |
|------|--------|------|
| `strategies/goldcombo/goldcombo_strategy_ashare_v4.py` (项目位置) | `9ebb2c0441820f90853eb9f4f270dd3540c2d8cfad766c2860f3ad3a55408eea` | 6744 B |
| `strategies/goldcombo/goldcombo_strategy_ashare.py` (alias 改指向 v4) | `7636ad8ed4e2a0459e867a5dba76f0416daa0f66d1622b520ccf3161df79ca45` | 13471 B |

alias 文件改动:
- 旧: `from strategies.goldcombo.goldcombo_strategy_ashare_v3 import GoldComboV3_1Strategy as GoldComboStrategy`
- 新: `from strategies.goldcombo.goldcombo_strategy_ashare_v4 import GoldComboV5Strategy as GoldComboStrategy`
- 头部 docstring 更新为 v4 版本管理说明

## import 自检

```
v4 direct import: GoldComboV5Strategy    ✓
alias import:      GoldComboV5Strategy    ✓
same class:        True                   ✓
```

alias 文件 `goldcombo_strategy_ashare.py` 仍可工作,实际类指向 v4。

## v4 vs v3 关键差异 (用户手动优化,subagent 未擅自改)

| 项 | v3 | v4 |
|----|----|----|
| 策略类名 | `GoldComboV3_1Strategy` | `GoldComboV5Strategy` |
| 硬止损 | 5% 固定 | ATR(14)*2.5 自适应 |
| 移动止盈 | 固定 8% trail | 阶梯式 (20%/10%/6% 分档) |
| MA10 均线离场 | 无 | 盈利>3% 跌破 MA10 离场 |
| 时间止损 | 无 | 持仓 20 天 + 盈利<3% 强制平仓 |
| C7 CCI | <-80 | <-70 (更敏感) |
| C8 -DI | >25 | >20 (更敏感) |
| 滑点 | 0.001 | 0.003 (3 倍,更保守) |
| price_min | 3.0 | 3.0 (保持) |

## 下一步

T2 · git commit 单一 commit 含 alias + v4 新文件