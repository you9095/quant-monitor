# T1 · V20_NoMA 零均线数值化版策略文件落盘 + git commit

**时间**: 2026-08-16
**任务**: 解 RTF + 写 V20_NoMA 策略文件 + 修改 alias 兼容文件 + git commit

## 1. 用户上传文件验证

- 路径: `~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V20_NoMA.rtf`
- 大小: 4200 字节
- 类型: Rich Text Format (RTF v1, code page 936)
- 头部: `{\rtf1\ansi\ansicpg936` ✅
- **SHA256**: `9021d4fb1537abb33d519fc85d1b9b5bc8249ef554c4e47d6d15ab256087fde2` ✅ (与用户原话预期完全一致)

## 2. RTF 解出 + Python 验证

- 解出文件: `/Users/junze/goldcombo_real_backtest/v20/T1_extract/goldcombo_strategy_v20_clean.txt`
- **行数**: 71 行 ✅ (与派单预期 78 行 RTF → 71 行 Python 一致)
- **第一行**: `import backtrader as bt` ✅
- **第二行**: `import math` ✅
- **类名**: `GoldComboV20_NoMA(bt.Strategy)` ✅
- **末尾**: `if __name__ == '__main__':` + `cerebro.broker.setcash(50000.0)` ✅ (硬编码锁死)
- **零 SMA 验证**: `grep -c "bt.ind.SMA\|bt.indicators.SMA"` = 0 (策略代码无任何 SMA/MA 调用) ✅
- **10 参数全对**: break_n=60/atr_period=14/atr_multi=3.0/cci_peak=100/cci_fall=80/trail_sl=0.35/hard_sl=0.15/price_min=1.0/cash_pct=0.95/cool_days=60 ✅
- **3 指标**: Highest(60)/ATR(14)/CCI(14) — 零 SMA ✅
- **入场**: 收盘价 > 60日 最高价(-1) + cooldown=0 (纯通道突破, 无均线) ✅
- **4 离场机制**: 15% 硬止损 / 35% 峰值回撤 / 3*ATR 断裂 / CCI 泡沫破灭 ✅
- **cooldown 60 日禁买**: V20 内部冷却机制 (`_reset()` 写入 self.cooldown = 60) ✅

## 3. 写入项目位置

- 目标: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v20.py`
- **写入 SHA256**: `c0b6c9b52a5f5596a05482cedcb9a3f63bc89d1787d4e58c28f1beb29e73373b`
- **diff 验证**: 与解 RTF 后的 clean.txt 仅末尾换行差异,内容完全一致 (一字不差) ✅
- **零外部 hold/lock**: 策略类无 self.lock / self.hold / self.lockday 等外部状态变量 ✅
- **零 SMA**: `grep -c "bt.ind.SMA\|bt.indicators.SMA"` = 0 ✅
- **零参数修改**: 10 参数原样保留 ✅
- **setcash 锁死**: 50000.0 ✅

## 4. alias 兼容文件修改

- 文件: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare.py`
- 头部注释: V17_LowFreqBreakout → V20_NoMA (零均线数值化版) ✅
- 主体 import: `from strategies.goldcombo.goldcombo_strategy_ashare_v20 import GoldComboV20_NoMA as GoldComboStrategy` ✅
- SHA256 记录: V20 用户上传 + 写入项目 + V17 旧类 git 历史 ✅

## 5. git commit

- **Commit SHA**: `7120228` (完整: `7120228...` 见 `git log -1 --format=%H`)
- **Commit message**: `feat(goldcombo): V17_LowFreqBreakout → V20_NoMA 零均线数值化版 (卖点剔除所有MA, 用具体数值/ATR/CCI)`
- **变更**: 2 files changed, 79 insertions(+), 6 deletions(-)
  - `A  strategies/goldcombo/goldcombo_strategy_ashare_v20.py` (新文件)
  - `M  strategies/goldcombo/goldcombo_strategy_ashare.py` (alias 改指向 V20)
- v1-v17 + V7FIXOBV git 历史完整保留 ✅

## 6. 硬约束符合性 (4 条 + 16 条)

1. ✅ **零策略修改**: V20_NoMA 策略类一字不差写入,与 RTF 解出文件 diff 仅末尾换行
2. ✅ **零外部 hold/lock**: 未添加任何 self.lock/self.hold/self.lockday,cooldown 是 V20 内部 `_reset()` 写入的 self.cooldown
3. ✅ **零 SMA/MA**: 策略类 0 个 SMA/MA 调用,3 指标全 Highest/ATR/CCI
4. ✅ **零参数修改**: 10 参数原样保留
5. ✅ **setcash(50000.0) 锁死**: 写入项目 + alias 注释双记录
6. ✅ **零 mock / stub / 占位**
7. ✅ **保留 v1-v17 + V7FIXOBV git 历史**

## 7. 产出

- ✅ git commit SHA: `7120228`
- ✅ V20 策略文件已落盘
- ✅ alias 已切换
- ✅ sha256 校验完成 (RTF + 写入项目双记录)
