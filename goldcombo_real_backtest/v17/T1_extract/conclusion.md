# T1: V17_LowFreqBreakout 策略文件落地 + git commit — PASS

## 验证项

### V17 用户上传文件 (RTF)
- 文件路径: `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合V17_LowFreqBreakout.rtf`
- 大小: **3909 B**
- 行数: **73 行 (RTF)**
- sha256: `f5ad37f33dbdda8c36a16587d36f9c38127d8ee0de84d897da2aa359947a71bd` ✅ **匹配预期**
- 文件头验证: `{\rtf1\ansi\ansicpg936\cocoartf2709...` ✅ 是 RTF

### RTF 解码 (textutil)
- 工具: `textutil -convert txt -inputencoding UTF-8 -encoding UTF-8`
- 输出文件: `/Users/junze/goldcombo_real_backtest/v17/T1_extract/goldcombo_strategy_v17_clean.txt`
- 解出 Python 行数: **66 行** ✅ 匹配预期 (73 → 66)

### 解出 Python 验证 (一字不差逐行检查)
- ✅ 第 1 行: `import backtrader as bt`
- ✅ 第 2 行: `import math`
- ✅ 第 4 行: `class GoldComboV17_LowFreqBreakout(bt.Strategy):` (类名锁定)
- ✅ 7 个参数全对:
  - `break_n=120` (半年突破)
  - `ma_short=20`
  - `ma_mid=60`
  - `ma_long=120` (多头序最后一根)
  - `trail_sl=0.20` (峰值回撤止盈)
  - `hard_sl=0.15` (硬止损)
  - `per_pos_pct=0.95` (集中持仓)
- ✅ 4 个指标 (极简, 范式革命 2.0):
  - `Highest(self.data.high, period=120)` (半年最高)
  - `SMA(period=20)` (MA 短期)
  - `SMA(period=60)` (MA 中期)
  - `SMA(period=120)` (MA 长期)
- ✅ 入场 (极严): `price > highest_n[-1]` (半年突破) + `MA20>MA60>MA120` (多头序)
- ✅ 离场 3 机制:
  - `price < entry_price * (1 - 0.15)` → 15% 硬止损
  - `price < highest_since_entry * (1 - 0.20)` → 20% 峰值回撤止盈
  - `price < ma_s[0]` → 收盘价跌破 MA20 短期生命线
- ✅ 仓位: `cash * 0.95` 95% 集中持仓 (单只满仓)
- ✅ 过滤: `price < 3.0` / `math.isnan(ma_l[0])` / `math.isnan(highest_n[0])` → return
- ✅ 末尾 `if __name__ == '__main__':` 含 `cerebro.broker.setcash(50000.0)` 硬编码锁死

### 写入项目位置
- 目标: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v17.py`
- sha256 (写入后): `50b10dde71fc9b64ec4757d508ad30a4b1028c7577f02894e28c9b265398cc17`
- 字节数: 2798 B (与解 RTF 文件字节一致 ✅)
- 行数: 66 行 (一字不差, 无任何修改)
- **未添加任何外部 hold/lock/sl 逻辑** (用户原话硬约束 V13 沿用)
- **未修改任何参数** (用户原话硬约束)
- **未改 setcash(50000.0)** (用户原话硬约束)
- **未加 V16 短周期指标** (V17 范式革命 2.0, 保持长周期 120/60/20)

### alias 文件修改
- 路径: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare.py`
- 头部注释: 5 处改为 V17 描述 (含 V17 与 V16 设计哲学差异 + V17 抛弃的 4 个 V16 短周期指标清单)
- alias import: `from strategies.goldcombo.goldcombo_strategy_ashare_v16 import GoldComboV16_ChannelBreakout as GoldComboStrategy`
  → `from strategies.goldcombo.goldcombo_strategy_ashare_v17 import GoldComboV17_LowFreqBreakout as GoldComboStrategy`
- 版本备份链新增: `V17_LowFreqBreakout 新文件: strategies/goldcombo/goldcombo_strategy_ashare_v17.py`
- sha256 行: V16 改为 V17 (`f5ad37f3...` / `50b10dde...`)
- V16 文件保留段新增 (作为废弃但保留 git 历史 commit 4f1345b)
- V8final/V9/V7FIXOBV 等其他历史行不动

### alias import 验证
```
$ python3.12 -c "from strategies.goldcombo.goldcombo_strategy_ashare import GoldComboStrategy; print(GoldComboStrategy.__name__)"
alias import OK: GoldComboV17_LowFreqBreakout
```
✅ alias 正确指向 V17

### git commit
- commit SHA: **`e2d105b22c20b1e7f9c2880c95f5bb2172f81cfc`**
- diff: 2 files changed, 94 insertions(+), 16 deletions(-)
- 新建: `strategies/goldcombo/goldcombo_strategy_ashare_v17.py`
- 修改: `strategies/goldcombo/goldcombo_strategy_ashare.py` (alias 指向 V17)
- v1-v16 + V7FIXOBV git 历史保留 (commit hygiene)

## 不做的事 (用户原话硬约束 4 条)
- ❌ **未修改 V17_LowFreqBreakout 策略类任何一行** (用户原话)
- ❌ **未加任何外部 hold/lock/sl 逻辑** (V13 沿用)
- ❌ **未擅自修改 V17 7 个参数**
- ❌ **未改 setcash(50000.0)** (用户原话硬约束)
- ❌ **未加 V16 短周期指标** (V17 范式革命 2.0)
- ❌ **未擅自修改 V16 / V14 / V13 / V12 / V11 / V10 / V7FIXOBV / V9 策略源码**

## 状态
**T1 PASS** ✅