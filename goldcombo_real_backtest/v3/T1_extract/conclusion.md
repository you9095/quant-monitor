# T1 · 解 RTF + 写 v3 策略文件 — 完成报告

## 1. v3 用户上传文件元信息
- 源文件: `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第三版.py`
- 大小: 6370 B
- 类型: `Rich Text Format data, version 1, ANSI, code page 936` (RTF 包裹的 Python)
- **用户原始文件 sha256**: `8cf94157d1db91367a657c2e414a287bd08c75817a3ecb6d973e754bfc28c0de`
- 解 RTF 时间: `2026-08-14T14:29:33Z`

## 2. 解 RTF 方法
**首选**: macOS 系统工具 `textutil -convert txt` (比 python re.sub 更稳,中文注释完整保留)
**备选**: python `re.sub(r'\\[a-z0-9]+\*? ?', '', raw)` 然后 `\\\\\n` → `\n` 替换

textutil 一次过:103 行完整 Python + 中文注释(类 docstring + 中文变量解释)全部保留。
python re.sub 方案失败:中文 unicode 段无法被简单正则恢复,会出现 `\\uc0\\u-` 残留。

## 3. 文件产出 (4 个)

### 3.1 raw 提取文件
- `/Users/junze/goldcombo_real_backtest/v3/T1_extract/goldcombo_strategy_v3_raw.py`
- 大小: 4444 B
- **sha256**: `45af259a1ebae70760d7cd27ded47130daaa7c5b330e3ed7c6df459efd7f9f7e`
- 内容: textutil 解出的真 Python (103 行)
- 验证: 第 1 行 `import backtrader as bt`,第 3 行 `class GoldComboV3_1Strategy(bt.Strategy):` ✅

### 3.2 项目位置 v3 文件 (新文件)
- `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v3.py`
- 大小: 5986 B (133 行,头 30 行注释 + 后 103 行真 Python)
- **sha256**: `f9e989104a807dcd0ea80a625bc7ed6053bba747ae48a22b427badefcbb1ae58`
- 内容: 头部 30 行含 sha256/解 RTF 时间/方法/v2→v3 变化清单注释,后接真 Python
- 与 v2 文件 `goldcombo_strategy_ashare_v2.py` 并存 ✅

### 3.3 alias 兼容文件 (改 import)
- `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare.py`
- 改动: 
  - 头注释从 "[v1 已废弃,新策略在 v2]" → "[v2 已废弃,新策略在 v3]"
  - 实际类从 `GoldComboRelaxedStrategy` → `GoldComboV3_1Strategy`
  - `from strategies.goldcombo.goldcombo_strategy_ashare_v2 import GoldComboRelaxedStrategy as GoldComboStrategy`
    →
    `from strategies.goldcombo.goldcombo_strategy_ashare_v3 import GoldComboV3_1Strategy as GoldComboStrategy`
- 验证 `from strategies.goldcombo.goldcombo_strategy_ashare import GoldComboStrategy` → 实际指向 `strategies.goldcombo.goldcombo_strategy_ashare_v3.GoldComboV3_1Strategy` ✅

### 3.4 未触碰文件确认
- `goldcombo_strategy.py` (ETF 池版) 未改 ✅
- `goldcombo_strategy_ashare_v2.py` sha256 仍为 `a16653578143b69a11d0f66e17697fcc19a53ee93611dbe78432fa8475bcaaa1` 与 T0 备份一致 ✅
- `goldcombo_strategy_ashare_v1_alias.py` 不存在 (v1 早就废弃,v2→v3 不再需要 v1 alias) ✅
- `ratchet_*.json` / `ratchet_baseline_*.json` 未改 ✅
- `monitor_*.html` 等前端文件未改 ✅

## 4. 完成度
- RTF 完整解开 ✅
- 真 Python 写到项目位置 ✅
- alias 文件改指向 v3 ✅
- v2 文件保持不变 ✅

T1 PASS — v3 策略文件就位,alias 已切换,可进入 T2 commit。
