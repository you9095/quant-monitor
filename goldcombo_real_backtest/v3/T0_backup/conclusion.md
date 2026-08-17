# T0 · v2 版本基线备份 — 完成报告

## 1. 备份前 git 状态
- 仓库: `/Users/junze/quant-monitor-local`
- 当前 HEAD: `da10a57 feat(goldcombo): v1 → v2 改良共振版 (Gated Voting C3+vote≥2)`
- 上一 commit: `4964e52 feat(ashare): 重启 A 股 K 线下载 + 修复 pool + 重写 signals/goldcombo_2026-08-13.json`
- 上上一 commit: `574bb44 refactor: 删除 ETF 池 2Y/5Y backtest JSON (替换为 A 股池)`
- 工作树:有大量未跟踪文件 (logs/audit/review/scripts 等) 与本次任务无关,goldcombo 策略目录未改动 → 安全覆盖

## 2. 备份文件清单 (5 个,全部 v2)

| 文件 | 大小 | sha256 |
|------|------|--------|
| `goldcombo_strategy_ashare.v2.py` | 3813 B | `a16653578143b69a11d0f66e17697fcc19a53ee93611dbe78432fa8475bcaaa1` |
| `goldcombo_strategy_ashare.v2_alias.py` | 12867 B | `c3016701b58ad04f996c4980ba8420abe0bdd797503d19853633c08e7915bffd` |
| `baseline_ashare_real_2y.v2.json` | 7486 B | `58731240a07b2d9d1ed5c69a3818aad431e507d0ba3166304f5c7d26604e2817` |
| `conclusion.v2.md` | 2354 B | `445f09bc2bf4881aeab80692cd089b9d72fcb9e25abd0a92955cbf312adea1f3` |
| `run_backtest_2y.v2.py` | 17152 B | `08d070e1f616d1b3f886ac27cd6c91eb722b368e0269eddfbb3f176e4778580e` |

## 3. 备份位置
`/Users/junze/goldcombo_real_backtest/v2_backup/`

## 4. 完成度
- 备份文件数: 5/5 ✅
- sha256 校验: 5/5 ✅
- v1 备份未触碰 (`/Users/junze/goldcombo_real_backtest/v1_backup/`) ✅

T0 PASS — v2 文件已完整备份,sha256 已记录,可进入 T1。
