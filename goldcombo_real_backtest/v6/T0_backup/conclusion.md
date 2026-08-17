# T0 · v4 版本基线备份结论

**任务**: v4 版本 5 个核心文件备份 + sha256 校验和

**备份目录**: `/Users/junze/goldcombo_real_backtest/v4_backup/`

**备份时间**: 2026-08-15 13:30

## 备份文件清单 (5 个)

| 文件 | 来源 | sha256 |
|------|------|--------|
| `goldcombo_strategy_ashare.v4.py` | `quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v4.py` | `9ebb2c0441820f90853eb9f4f270dd3540c2d8cfad766c2860f3ad3a55408eea` |
| `goldcombo_strategy_ashare.v4_alias.py` | `quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare.py` | `7636ad8ed4e2a0459e867a5dba76f0416daa0f66d1622b520ccf3161df79ca45` |
| `baseline_ashare_real_2y.v4.json` | `goldcombo_real_backtest/v4/T4_2y/baseline_ashare_real_2y_v4.json` | `faa9ba526c582f632060302396f89e9f8a65c488f68e24dcdbaac0344d2e73b8` |
| `raw_output.v4.log` | `goldcombo_real_backtest/v4/T4_2y/raw_output.log` | `178d262054dd693068edaeabf51338db694c57806e9cc2c588feec6726928d7b` |
| `run_backtest_2y.v4.py` | `goldcombo_real_backtest/v4/T4_2y/run_backtest_2y_v4.py` | `97c2de2de89c7844622738dfd41dad4c7ad61e046caf834ab73e9518f45e62c3` |

## v4 备份链状态

- ✅ v1 备份: `~/goldcombo_real_backtest/v1_backup/` (历史, 不动)
- ✅ v2 备份: `~/goldcombo_real_backtest/v2_backup/` (历史, 不动)
- ✅ v3 备份: `~/goldcombo_real_backtest/v3_backup/` (历史, 不动)
- ✅ v4 备份: `~/goldcombo_real_backtest/v4_backup/` (本次新建, 5 文件 + sha256)

## git 当前状态 (备份前)

```
e91db0e feat(goldcombo): v3 → v4 灵活卖点版 (ATR 自适应止损 + 阶梯移动止盈 + 时间止损)
57267e1 feat(goldcombo): v2 → v3 小资金严控版 (5% 硬止损 + 8% 移动止盈 + 价格过滤)
da10a57 feat(goldcombo): v1 → v2 改良共振版 (Gated Voting C3+vote≥2)
```

**说明**: v1→v2→v3→v4 三个 commit 都在 HEAD 链上,版本管理链路完整。备份完成后, T1 可以放心覆盖策略代码。

## T0 状态

**T0 (v4 备份): PASS** ✅

- 备份文件数: 5/5 ✅
- sha256 校验: 5/5 ✅
- git 状态记录: ✅