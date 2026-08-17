# T1 · 解 RTF + 写 v6 策略文件结论

**任务**: 解 RTF 取 v6 真 Python + 写 v6 策略文件到项目 + 改 alias 文件指向 v6

## v6 用户上传文件信息

- **文件路径**: `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V6版本.py`
- **文件大小**: 5806 字节
- **sha256**: `3fc45cd06f57f654bfc78ed9ba82cf53b42c8290fb88fee49a6b37c3fe245726`
- **头部确认**: `{\rtf1\ansi\ansicpg936\cocoartf2709` → **RTF 包裹的 Python** ✅

## RTF 解码结果

**方法**: `textutil -convert txt -inputencoding UTF-8 -encoding UTF-8 -output ...` (首选, macOS 原生)

**解码产出**: `/Users/junze/goldcombo_real_backtest/v6/T1_extract/goldcombo_strategy_v6_clean.txt` (4007 字节, 88 行)

**关键验证**:
- ✅ `import backtrader as bt` 在第 1 行
- ✅ `class GoldComboV6Strategy(bt.Strategy):` 第 3 行 (类名正确)
- ✅ Python 语法完整, 无 RTF 标签残留
- ✅ 4 个卖点机制齐全: 硬止损/保本/CCI>120/MACD 高位死叉
- ✅ 4 个 v4 错杀机制确认删除: ATR 自适应 / 阶梯止盈 / MA10 / 时间止损
- ✅ 入场核心 C3+C4/C7/C8 投票与 v4 一致

## v6 策略文件落盘

### 项目位置 v6 文件
- **路径**: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v6.py`
- **sha256**: `81448f57bec88405aeebfe9a9b71bf64eca05e1875fab27d3614980d7f7df61c`
- **内容**: 解 RTF 后的真 Python + 顶部注释 (来源 sha256 + 解 RTF 时间 + 备份链 + v6 vs v4 差异)
- **lint**: ✅ ok

### alias 文件 (goldcombo_strategy_ashare.py) 改指向 v6
- **修改前**: `from strategies.goldcombo.goldcombo_strategy_ashare_v4 import GoldComboV5Strategy as GoldComboStrategy`
- **修改后**: `from strategies.goldcombo.goldcombo_strategy_ashare_v6 import GoldComboV6Strategy as GoldComboStrategy`
- **头部注释**: 完整更新到 v6 (2026-08-15 版本管理 v6)
- **lint**: ✅ ok

## v3 + v4 文件未被修改验证

| 文件 | sha256 | 类名 | 状态 |
|------|--------|------|------|
| `goldcombo_strategy_ashare_v3.py` | (未变) | `GoldComboV3_1Strategy` | ✅ 保留 |
| `goldcombo_strategy_ashare_v4.py` | `9ebb2c0441820f90853eb9f4f270dd3540c2d8cfad766c2860f3ad3a55408eea` | `GoldComboV5Strategy` | ✅ 保留, sha256 与 v4 backup 一致 |

## v6 vs v4 关键差异 (已写入策略文件头部注释)

- **5% 硬止损回归**: `hard_sl=0.05` (v3 → v4 删除, v6 拿回)
- **新增保本移动止损**: `breakeven_pct=0.05` + `be_stop_pct=0.01`
- **MACD 高位死叉离场回归**: DIFF 下穿 DEA 且都在零轴上
- **彻底删除**: ATR 自适应止损 / 阶梯移动止盈 / MA10 跌破 / 时间止损
- **保留**: CCI>120 离场
- **入场核心 (C3+C4/C7/C8)** 和 C7/C8/price_min/cash_pct/滑点 与 v4 一致

## T1 状态

**T1 (解 RTF + 写 v6): PASS** ✅

- 解 RTF 方法: `textutil -convert txt` ✅
- v6 文件 sha256: `81448f57bec88405aeebfe9a9b71bf64eca05e1875fab27d3614980d7f7df61c` ✅
- v6 类名: `GoldComboV6Strategy` ✅
- v3/v4 文件保留: ✅
- alias 指向 v6: ✅