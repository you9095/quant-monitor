# T1 · 解 RTF + 写 V12 + commit — PASS

## 用户文件验证
- 路径: `/Users/junze/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合v12-leftbuy.rtf`
- 大小: 4861 B
- sha256: `8274271cd2bcb9ae71376e7a30484b7487cfdb2b97047f46224280706951e8d5` ✅ 匹配预期
- 头部验证: `{\rtf1\ansi\ansicpg936\cocoartf2709` ✅ 真实 RTF

## 解 RTF
- textutil 转换成功 → `goldcombo_strategy_v12_clean.txt`
- 行数: 77 行 ✅ 匹配预期 (RTF 84 → Python 77)
- 首行: `import backtrader as bt` ✅
- 类名: `GoldComboV12_LeftBuyRightSell(bt.Strategy)` ✅
- 末行: `if __name__ == '__main__':` + `cerebro.broker.setcash(50000.0)` 硬编码 ✅

## V12 写入项目
- 目标: `/Users/junze/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v12.py`
- 内容: 77 行 Python 一字不差 (含 setcash(50000.0))
- 写入 sha256: `2c52b145c93f2e622f90b5727c3d57b83cde3f489777b352c229d16f56d0cccb`
- 9 参数全保留: cci_thresh=-70/di_neg=20/di_pos=15/vote_min=1/price_min=3.0/per_pos_pct=0.10/hard_sl=0.30/trail_sl=0.25
- 无任何外部 hold/lock 逻辑

## alias 文件
- 路径: `strategies/goldcombo/goldcombo_strategy_ashare.py`
- import 改: `GoldComboV12_LeftBuyRightSell as GoldComboStrategy`
- 文件头部注释说明现在指向 V12 (V11 已废弃, 保留 git 历史)

## git commit
- commit SHA: **`925efd4f066f8c8d811b2b5df17ffd90f0db63fb`**
- 提交内容: 2 files changed, 81 insertions(+), 3 deletions(-)
  - M strategies/goldcombo/goldcombo_strategy_ashare.py (alias 指向 V12)
  - A strategies/goldcombo/goldcombo_strategy_ashare_v12.py (新增 V12 用户原版)

## V12 设计哲学
- 左买右卖混合版 — 买点左侧 (C3+≥1) + 卖点右移 (破MA20+DMI空方反扑)
- 入场: C3 MACD 低位金叉必选 + [C4 BOLL扩口 / C7 CCI<-70 / C8 DMI空方] ≥1 投票
- 离场 3 机制:
  1. 30% 硬止损 (同 V10 路径 B 宽容)
  2. 25% 峰值回撤止盈 (同 V10 路径 B)
  3. 能量终结离场 (右移卖点, 关键变更): 价格破 MA20 且 DMI 空方反扑 (+DI<10 且 -DI>25)
- 仓位: 10% 组合分仓 (复刻 V10 路径 B 5000/只)
- 强制本金: setcash(50000.0) 锁死

## 6 条硬约束遵守检查
1. ❌→✅ 未修改 V12 策略类任何一行
2. ❌→✅ 未加任何外部 hold/lock/sl 逻辑
3. ❌→✅ 未擅自修改 V12 9 个参数
4. ❌→✅ setcash(50000.0) 锁死保留
5. ❌→✅ 1950 沪深 A 股池 (后续 T4 用)
6. ❌→✅ 不准用 ETF 池 (后续 T4 用 A 股)
