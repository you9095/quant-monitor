# T1 · V11_EnergyPeak 用户原版落盘 + git commit — PASS

## 用户上传文件验证

- **路径**: `~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合v11-energypeak.rtf`
- **大小**: 3360 B
- **sha256**: `6ceb76b0f1c633b8dfa673ed5b6ff16c62da3ba5c87666781335d49702b5ac8a` ✅ 匹配预期
- **行数**: 68 行 (RTF) → 61 行 Python ✅ 匹配预期

## RTF 解出验证 (一字不差)

`textutil -convert txt -inputencoding UTF-8 -encoding UTF-8` 解出 `goldcombo_strategy_v11_clean.txt`:

- ✅ 第一行 `import backtrader as bt` + `import math`
- ✅ 类名 `GoldComboV11_EnergyPeak(bt.Strategy)` (一字不差锁定)
- ✅ 10 个参数全对: cci_thresh=-70 / di_neg_thresh=20 / di_pos_thresh=15 / vote_min=1 / price_min=3.0 / per_pos_pct=0.20 / hard_sl=0.15 / trail_sl=0.20 / cci_peak=100 / cci_fall=80
- ✅ `if __name__ == '__main__':` 块末 `cerebro.broker.setcash(50000.0)` 硬编码 (用户原话硬约束, 不准改回 1万)
- ✅ 三种离场机制: 15% 硬止损 / 20% 峰值回撤 / CCI 能量衰竭 (5日前>100 现<80 破MA10)
- ✅ 入场: C3 必选 (MACD 低位金叉) + [C4 BOLL开口 / C7 CCI<-70 / C8 DMI空方] ≥1 投票

## V11 写入验证 (一字不差)

- **目标路径**: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v11.py`
- **解 RTF 后 / 写入 sha256**: `fa77395a495b3dbb6b5afec02227ac835be3e511ad3457c7f4ae4bf3279e39e8`
- ✅ 解 RTF 后文件与写入项目位置文件 SHA 完全一致 (cp 命令验证, 一字不差)

## alias 文件修改

`goldcombo_strategy_ashare.py`:
- import: `from strategies.goldcombo.goldcombo_strategy_ashare_v11 import GoldComboV11_EnergyPeak as GoldComboStrategy`
- 文件头部 docstring 已更新: V10_HighYield 标记为已废弃, V11_EnergyPeak 当前生效
- V10/V9/V8final/V7FIXOBV/V6 文件全部保留为 git 历史
- ✅ alias import 验证: `GoldComboStrategy.__name__` = `GoldComboV11_EnergyPeak`

## 用户原话硬约束遵守

- ❌ 未修改 V11_EnergyPeak 策略类任何一行
- ❌ 未加任何外部 hold/lock/sl 逻辑
- ❌ 未擅自修改 V11 10 个参数
- ❌ 未改 setcash(50000.0) (硬编码保留)
- ❌ 未擅自修改 V10_HighYield / V7FIXOBV / V8final / V9 策略源码 (git 历史保留)
- ❌ 未改 v6 / v3 / v4 等旧策略源码

## git commit

- **commit SHA**: `097062c629504da92d7ee57c430120d805da4118`
- **commit message**: `feat(goldcombo): V10_HighYield → V11_EnergyPeak 能量衰竭离场 (5万本金锁死, 不准改 1万)`
- **变更**: 2 files changed, 82 insertions(+), 17 deletions(-)
- **新文件**: `strategies/goldcombo/goldcombo_strategy_ashare_v11.py` (mode 100644)
- **修改**: `strategies/goldcombo/goldcombo_strategy_ashare.py` (alias 指向 V11)

## git 历史链

```
097062c feat(goldcombo): V10_HighYield → V11_EnergyPeak 能量衰竭离场 (5万本金锁死, 不准改 1万)
f040379 feat(goldcombo): V7FIXOBV → V10_HighYield 激进左翼高收益版 (用户军令状: 死磕左侧)
40b73a4 feat(goldcombo): V7LOCK v2 → V7FIXOBV 用户原版 (OBV bug 修复)
19f1cde feat(goldcombo): V7LOCK v1 → v2 完整版 (用户重传完整 buy 算法)
c514fdd feat(goldcombo): V8final → V9 用户原版 (一字不差, 不准加 hold/lock)
67a5f98 feat(goldcombo): V8final 替换 v8 EatTheBody (终极版, 仅策略类更新)
```
