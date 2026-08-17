# T0 版本基线备份 — 结论

## git 状态快照 (备份前)

工作区: 干净但有大量 untracked files (其他子任务遗留):
- M api/real_data_server_v2.py
- M index.html
- M logs/.alert_state.json
- M scripts/quant_data_sync.py
- ?? 大量 logs/ review/ scripts/ (本次任务不动)

最近 5 个 commits:
```
4964e52 feat(ashare): 重启 A 股 K 线下载 + 修复 pool + 重写 signals/goldcombo_2026-08-13.json
574bb44 refactor: 删除 ETF 池 2Y/5Y backtest JSON (替换为 A 股池)
ed05120 fix(P1): 5Y 数字诚实更正 (14.23% → 0.2557%)
5d5811d fix(P0): V5 signals/goldcombo_2026-08-12.json 重写 (A 股池替换 ETF 池)
7f8f8f7 docs(changelog): 记录 goldcombo 集成 + P0 fix 三 commit
```

## v1 文件备份 (5 个文件 → ~/goldcombo_real_backtest/v1_backup/)

| 文件 | 大小 | sha256 |
|------|------|--------|
| goldcombo_strategy_ashare.v1.py | 12455 | 8aa844ab9bc304803b99a29fff5862c037594ef72299f0f96d3f90b49f087190 |
| goldcombo_strategy.v1.py | 17521 | 1d7e83b72458b600b31a391226801d090bc85c9ff37f75e4dadae6efe9b99a7f |
| baseline_ashare_real_2y.v1.json | 5884 | fe33fde25560f328ae276a8c9d5ae31847c15df1760f80931d094d2274580280 |
| conclusion.v1.md | 2575 | 0be952f62f141e28397bc63da617b814d806b6e5a4aa0d280fbb14442d23a0b5 |
| run_backtest_2y.v1.py | 14193 | b0ab8851824200d917882497e245dd6d23a8a6c0d423352624d3d48dbbfb777d |

## v2 源文件信息 (用户上传)

- 路径: ~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化第二版.py
- 大小: 5284 字节
- ⚠️ **格式陷阱**:扩展名 .py 但内容是 RTF 包装 (`{\rtf1\ansi...}`),macOS TextEdit 误保存导致
- 已用 `textutil -convert txt` 剥离 RTF 头,得到纯 Python 90 行
- RTF 包装原文件 sha256: `4f1be4174abcafb88ec3443cc50629c2c84df3a9c341d1739fca4e15469ea6fe`
- 剥离 RTF 后 v2 策略代码 sha256: `a16653578143b69a11d0f66e17697fcc19a53ee93611dbe78432fa8475bcaaa1`

## v2 关键参数 (来自源码)

- 入场: C3 必选 (MACD 低位金叉) + [C4/C7/C8] 辅助 ≥ 2 投票
- C3: macd[0] > signal[0] AND macd[-1] <= signal[-1] AND macd[0] < 0
- C4: bw > bw_prev (BOLL 开口)
- C7: cci < -80 (放宽自 -100)
- C8: plus_di < 15 AND minus_di > 25 (放宽自 10/30)
- 止损: -8%
- 出场: CCI>120 OR (DMI 多方 +ADX>32) OR TRIX 水上 OR MACD 水上
- 初始资金: 100000

T0 状态: **PASS**
