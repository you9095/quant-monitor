# T1 · V10_HighYield 解 RTF + 写入 + git commit

**结果**: PASS

## 1. 验证 V10_HighYield 用户上传文件

```
文件:    ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合v10-highyield.rtf
大小:    5139 B
sha256:  d311c85ea03f3c20fd30d8ebb0c50629804412cfdf6379334df04a445a0deed0 ✅ 与预期完全匹配
格式校验: {\rtf1\ansi\ansicpg9... ✅ 真 RTF 格式 (RTF magic number 7b5c 7274 6631)
```

## 2. 解 RTF 结果

```
textutil -convert txt 解出: goldcombo_strategy_v10_clean.txt
行数:  77 行 ✅ (预期 77 行 Python)
首行: import backtrader as bt ✅
次行: import math ✅
类名: GoldComboV10_HighYield(bt.Strategy) ✅ (在第 4 行)
末行: cerebro.run() ✅ (第 77 行, 无截断)
主入口: if __name__ == '__main__': ✅ (第 72 行, 含完整跑批脚本)
9 参数: cci_thresh/di_neg_thresh/di_pos_thresh/vote_min/price_min/per_pos_pct/hard_sl/trail_sl/cci_bubble ✅
```

## 3. 一字不差写入项目位置

```
目标: /Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v10.py
写入 sha256: cd6d828ae20431c5f13b6ab4870d7195db41bfe926bbd4020583206abce9f8b0
解 RTF sha256: cd6d828ae20431c5f13b6ab4870d7195db41bfe926bbd4020583206abce9f8b0
diff 验证: 0 行差异 ✅ 完全 verbatim
```

## 4. alias 文件更新

```
文件: strategies/goldcombo/goldcombo_strategy_ashare.py (M)
变更:
  - 文件头注释: V7FIXOBV → V10_HighYield
  - import 改: from strategies.goldcombo.goldcombo_strategy_ashare_v10 import GoldComboV10_HighYield as GoldComboStrategy
  - 来源 sha256 改: d311c85e... (RTF) / cd6d828a... (Python)
AST 解析: OK ✅
```

## 5. git commit

```
commit SHA: f0403796ab2e061a4d06a5a7692b73d035bc29e3
变更: 2 files changed, 100 insertions(+), 39 deletions(-)
     1 file created (goldcombo_strategy_ashare_v10.py)
git 历史保留: v1-V7FIXOBV 历史未变 (40b73a4/19f1cde/c514fdd/67a5f98 都在)
```

## 6. V10_HighYield 关键参数摘要 (用于 T4 5Y 跑批)

```
入场逻辑: C3 必选 + [C4 BOLL 开口 / C7 CCI<-70 / C8 DMI 空方] ≥ 1 投票
离场 3 机制:
  - 30% 硬止损 (防退市) hard_sl=0.30
  - 25% 峰值回撤止盈 trail_sl=0.25
  - CCI>200 泡沫顶 cci_bubble=200.0
仓位: 单票 20% 现金 per_pos_pct=0.20 (组合分仓)
价格过滤: price_min=3.0 (防爆雷)
数据防火墙: math.isnan 防护 (MACD/CCI/+DI/-DI 任一 NaN return)
```

## 7. 硬约束自检 (用户原话)

- [x] 不修改 V10_HighYield 策略类任何一行
- [x] 不加任何外部 hold/lock/sl 逻辑
- [x] 不擅自修改 V10 9 个参数
- [x] V7FIXOBV/V8final/V9 源码未动 (保留 git 历史)
- [x] v3/v4/v6 旧策略源码未动
- [x] 单一 commit (用户 P0 commit hygiene)
- [x] 来源 sha256 校验落库 (用户 P0)