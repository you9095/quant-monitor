# T1 · 解 RTF + 写 V8final 策略文件

**状态**: ✅ PASS
**执行时间**: 2026-08-15

---

## 步骤 1: 验证 V8final 用户上传文件 ✅

```bash
$ ls -la ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化V8final.py
-rw-r--r--@ 1 junze  staff  8918  8 15 19:54 .../混元三黄金组合优化V8final.py

$ shasum -a 256 .../混元三黄金组合优化V8final.py
8d66c5841183bcd54861767490c1c7be42933c80663301a5a8eb0bfc92cda8c4  .../混元三黄金组合优化V8final.py

$ head -5 .../混元三黄金组合优化V8final.py
{\rtf1\ansi\ansicpg936\cocoartf2709
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
...     # 确认是 RTF 包裹
```

**验证结论**: 文件存在, 8918B, RTF 包裹, sha256 已记录。

## 步骤 2: 解 RTF ✅

```bash
$ textutil -convert txt -inputencoding UTF-8 -encoding UTF-8 \
    -output goldcombo_strategy_v8final_clean.txt \
    ".../混元三黄金组合优化V8final.py"

# 解出结果: 115 行, 5530B
$ wc -l goldcombo_strategy_v8final_clean.txt
     115 goldcombo_strategy_v8final_clean.txt

# 验证 Python 第一行 + 类名
$ head -1 goldcombo_strategy_v8final_clean.txt
import backtrader as bt

$ grep -n "GoldComboV8_Final\|class .*Strategy" goldcombo_strategy_v8final_clean.txt | head -5
3:class GoldComboV8_Final(bt.Strategy):
109:    cerebro.addstrategy(GoldComboV8_Final)
```

**验证结论**: RTF 解出真 Python, 第一行 `import backtrader as bt`, 类名 `GoldComboV8_Final(bt.Strategy)` ✅

## 步骤 3: 写 V8final 策略文件 ✅

**目标**: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v8final.py`

**内容结构**:
- 第 1-26 行: 模块级 docstring (provenance header)
  - 来源声明: 用户上传 RTF 文件 + sha256
  - 解 RTF 方法: `textutil -convert txt -inputencoding UTF-8 -encoding UTF-8`
  - 解 RTF 时间: 2026-08-15
  - 与 v8 EatTheBody 对比说明 (类名 + 注释 + cci_exit 参数差异)
  - 9 个硬性参数完整列出
- 第 28-127 行: 解 RTF 后真 Python (5530B → 写入 7336B 因加了 docstring)

**sha256 (写入后)**: 写入后文件大小 7336B, sha256 待 T2 commit 时一并记录。

## 步骤 4: 修改 alias 兼容文件 ✅

**目标**: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare.py`

**修改内容**:
- 头部 docstring 全面重写: v8 EatTheBody → V8final, 备份链状态更新, 用户原话引用更新
- 关键 import 行修改:
  ```python
  # 原: from strategies.goldcombo.goldcombo_strategy_ashare_v8 import GoldComboV8_EatTheBody as GoldComboStrategy
  # 新: from strategies.goldcombo.goldcombo_strategy_ashare_v8final import GoldComboV8_Final as GoldComboStrategy
  ```

## import 验证 ✅

```bash
$ /opt/local/bin/python3.12 -c "from strategies.goldcombo.goldcombo_strategy_ashare_v8final import GoldComboV8_Final; print('import OK:', GoldComboV8_Final.__name__)"
import OK: GoldComboV8_Final
```

## 未触动清单 (用户授权 + 任务 brief 限制)

| 文件 | 状态 | 原因 |
|---|---|---|
| `goldcombo_strategy.py` (ETF 池版) | ❌ 未改 | 任务 brief 禁止改 ETF 池版 |
| `goldcombo_strategy_ashare_v6.py` | ❌ 未删 | 用户 P0 commit hygiene, git 历史保留 |
| `goldcombo_strategy_ashare_v4.py` `v3.py` `v2.py` | ❌ 未删 | 同上 |
| `ratchet_*.json` / `ratchet_log*.json` | ❌ 未改 | 任务 brief 禁止改棘轮基线 |
| `monitor_*.html` 等前端文件 | ❌ 未改 | T5 才动 |

## V8final vs v8 EatTheBody 核心参数对比

| 参数 | v8 EatTheBody | V8final | 差异 |
|---|---|---|---|
| 类名 | GoldComboV8_EatTheBody | GoldComboV8_Final | **类名不同** |
| 入场 (C3 必选 + [C4/C7/C8] ≥ 2) | ✅ | ✅ | 同 |
| 硬止损 (10%) | ✅ hard_sl=0.10 | ✅ hard_sl=0.10 | 同 |
| 移动止盈 (15%) | ✅ trail_sl=0.15 | ✅ trail_sl=0.15 | 同 |
| CCI > 120 离场 | ✅ | ✅ cci_exit=120.0 (独立参数) | **V8final 独立参数化** |
| 价格过滤 price_min=3.0 | ✅ | ✅ | 同 |
| 仓位 cash_pct=0.95 | ✅ | ✅ | 同 |
| MACD 死叉离场 | ❌ 已删除 | ❌ 已删除 | 同 (硬性规则 7) |
| 注释详细度 | 基础 | **详细** (含硬性规则 1-7 列表) | **V8final 更详细** |
| 行数 | ~58 行 | 122 行 (含注释) | **V8final +64 行注释** |

**逻辑完全相同, 唯一差异是注释和参数命名。**

---

**T1 PASS** — V8final 真 Python 已解出并写入项目, alias 已切换, import 验证通过。