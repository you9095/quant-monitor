# T0 · v3 版本基线备份 — 结论

**执行时间**: 2026-08-14 23:00
**任务**: 在 v3 → v4 替换前,备份所有 v3 关键文件 + sha256 校验
**状态**: PASS

## git 状态(备份前)

```
57267e1 feat(goldcombo): v2 → v3 小资金严控版 (5% 硬止损 + 8% 移动止盈 + 价格过滤)
da10a57 feat(goldcombo): v1 → v2 改良共振版 (Gated Voting C3+vote≥2)
4964e52 feat(ashare): 重启 A 股 K 线下载 + 修复 pool + 重写 signals/goldcombo_2026-08-13.json
```

最近一次提交是 v2→v3 (57267e1),v3 策略代码和 alias 文件已落 git。
工作区存在大量其他 WIP 改动(api/real_data_server_v2.py, index.html, logs/, review/ 等),
但 strategies/goldcombo/ 关键文件当前未修改(无需再次备份)。

## v3 备份文件清单(sha256 校验)

| 文件 | sha256 | 大小 |
|------|--------|------|
| `goldcombo_strategy_ashare.v3.py` | `f9e989104a807dcd0ea80a625bc7ed6053bba747ae48a22b427badefcbb1ae58` | 5986 B |
| `goldcombo_strategy_ashare.v3_alias.py` | `fa314ba627a8485fcf7985544e447fbcef8e04a9ab768bbbc4c1fc9d835cc988` | 13296 B |
| `run_backtest_2y.v3.py` | `239a692d292f21520afcd3432e2d4d25e948df1bfbbe33bcfc7b8030f90f1526` | 13458 B |
| `baseline_ashare_real_2y.v3.json` | `6329e7c2b36647df03b55875ad1a12b1da1163ac6fd98dcada1fafa04171da0f` | 8275 B |

**说明**: task spec 列了"5 个文件"但实际 cp 命令只有 4 个。
已存在的源文件就是这 4 个:v3 策略类 + v3 alias + v3 baseline json + v3 回测脚本。
无遗漏关键文件。

## v3 历史指标(回填)

- 33 只成交
- 33 笔交易
- +0.0571% 收益
- 价格过滤剔除 315 只 (沪深全 A 股 1950 只池)
- 数据期 2024-08-14 ~ 2026-08-14

## 备份路径

`/Users/junze/goldcombo_real_backtest/v3_backup/`

含 `sha256sums.txt` + 4 个 v3 文件。完整备份链:

| 版本 | 备份路径 | git commit |
|------|---------|-----------|
| v1 | `~/goldcombo_real_backtest/v1_backup/` | da10a57 (v1→v2) |
| v2 | `~/goldcombo_real_backtest/v2_backup/` | 57267e1 (v2→v3) |
| v3 | `~/goldcombo_real_backtest/v3_backup/` (本次新建) | 待 v3→v4 commit |

## 下一步

T1 · 解 RTF + 写 v4 策略文件