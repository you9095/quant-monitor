# T1 · 解 RTF + 写 V16 + git commit — PASS

## RTF 来源验证
- **路径**: `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V16_ChannelBreakout.rtf`
- **大小**: 3396 bytes
- **行数**: 59 行 (RTF) → 52 行 Python (解 RTF 后)
- **sha256**: `65dac3f0f445e3aec5162e13e8ce60ff010f0d248c3ca078e7c5ca1d78242652` ✅ 预期一致
- **文件头**: `{\rtf1\ansi\ansicpg936\cocoartf2709` ✅ 真 RTF

## 解 RTF (textutil)
- 输出: `/Users/junze/goldcombo_real_backtest/v16/T1_extract/goldcombo_strategy_v16_clean.txt`
- 行数: 52 ✅ (RTF 59 行 → Python 52 行)
- 第 1 行: `import backtrader as bt` ✅
- 第 2 行: `import math` ✅
- 第 4 行: `class GoldComboV16_ChannelBreakout(bt.Strategy):` ✅
- 第 50 行: `cerebro.broker.setcash(50000.0)` ✅ 硬编码锁死
- 5 参数 (line 17): `break_out=20, break_down=10, ma_filter=50, atr_period=14, risk_pct=0.02` ✅

## V16 文件落盘
- **目标**: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v16.py`
- **sha256 (写入项目)**: `a8ab136b14dd52a9a243c34dae31fe951207cefe7d2edfa07c4510b92576db99`
- **sha256 (clean.txt)**: `a8ab136b14dd52a9a243c34dae31fe951207cefe7d2edfa07c4510b92576db99`
- **一致性**: ✅ **完全一致, 一字不差** (V16 范式革命, 含 setcash(50000.0) 锁死, 4 指标 Highest/Lowest/ATR/SMA)

## V16 设计哲学 (范式革命)
- **彻底抛弃**: MACD / CCI / DMI / BOLL / MA10
- **4 指标**: Highest(20日高) / Lowest(10日低) / ATR(14日) / SMA(50日)
- **入场 (唐奇安)**: 收盘价 > 20日最高价(-1) AND 价格 > 50日 SMA (多头)
- **离场**: 收盘价 < 10日最低价(-1) OR 成本回撤 > 2×ATR
- **仓位 (ATR 波动率定仓)**: `size = int(cash × 2% / (ATR × 100)) × 100` — 波动大买少, 波动小买多
- **过滤**: price < 3.0 OR ATR is NaN → return (双过滤)

## alias 文件修改 (`goldcombo_strategy_ashare.py`)
- 旧 import: `from strategies.goldcombo.goldcombo_strategy_ashare_v14 import GoldComboV14_ScaleIn as GoldComboStrategy`
- **新 import**: `from strategies.goldcombo.goldcombo_strategy_ashare_v16 import GoldComboV16_ChannelBreakout as GoldComboStrategy` ✅
- 文件头注释: V14_ScaleIn → V16_ChannelBreakout 范式革命版 ✅
- V14 已废弃声明保留, git 历史 commit c27d509 ✅

## git commit (T1)
- **SHA**: `4f1345b5a55479baac6467456edef294ffd40399`
- **分支**: master
- **变更**: 2 files changed, 71 insertions(+), 17 deletions(-)
- **新文件**: `strategies/goldcombo/goldcombo_strategy_ashare_v16.py` (52 行, V16 范式革命)

## 硬约束自检 (4 条)
- ✅ V16 类一字未改 (sha256 一致)
- ✅ 未加外部 hold/lock/sl
- ✅ 5 参数未动
- ✅ setcash(50000.0) 未改
- ✅ V16 范式革命, 未加 MACD/CCI/DMI
- ✅ V14/V13/V12/V11/V10/V9/V7FIXOBV 源码未动 (git 历史保留)

## T1 结论: **PASS**