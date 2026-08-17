# T0 · 清理 v1-v6 旧回测数据

**状态**: ✅ PASS (核心清理清单已完成)
**执行时间**: 2026-08-15
**用户授权**: 原话 "删除掉原先所有的旧数据" (§7 破坏性双确认豁免)

---

## 清理清单 (按 brief 显式列出)

### 已删除 ✅

| 路径 | 内容 | 原因 |
|---|---|---|
| `~/goldcombo_real_backtest/v1_backup/` | v1 备份链 | 用户授权清理 |
| `~/goldcombo_real_backtest/v2_backup/` | v2 备份链 | 用户授权清理 |
| `~/goldcombo_real_backtest/v3_backup/` | v3 备份链 | 用户授权清理 |
| `~/goldcombo_real_backtest/v4_backup/` | v4 备份链 | 用户授权清理 |
| `~/goldcombo_real_backtest/v6_5y/` | v6 5Y 跑批产物 | 用户授权清理 |
| `~/goldcombo_real_backtest/v6_etf/` | v6 ETF 跑批产物 | 用户授权清理 |
| `~/goldcombo_real_backtest/v6_monitor/` | v6 monitor 集成产物 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T0_backup/` | v8 T0 任务 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T1_extract/` | v8 T1 任务 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T2_commit/` | v8 T2 任务 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T3_smoke/` | v8 T3 任务 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T4_5y/` | v8 T4 任务 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T5_monitor/` | v8 T5 任务 | 用户授权清理 |
| `~/goldcombo_real_backtest/v8/T6_verify/` | v8 T6 任务 | 用户授权清理 |
| `~/quant-monitor-local/strategies/goldcombo/goldcombo_strategy_ashare_v8.py` | 旧 v8 EatTheBody 源码 | 用户原话 "V8 源代码直接替换上去" |

### 已重命名 ✅
- `~/goldcombo_real_backtest/v8/` → `~/goldcombo_real_backtest/v8_old_eatthebody_backup/`
  - 内含 `v6_integration_backup/` (v8 集成快照, 仅保留此 6 文件目录)
  - 原 v8 任务产物已全部删除

### 已备份 ✅
- `~/goldcombo_real_backtest/v8final/_v6_monitor_backup/`:
  - `goldcombo_signal.v6_5y.json` (v6 5Y signal 快照)
  - `index.html.v6_5y` (v6 5Y index.html 快照)
  - `strategies.v6_5y.json` (v6 5Y strategies.json 快照)
  - 用途: T5 完成后可删除, 仅作 fallback

## 保留清单 (未触动)

| 路径 | 内容 | 原因 |
|---|---|---|
| `~/quant-monitor-local/strategies/goldcombo/*.py` (除 v8) | v1-v7 + ETF 池 + alias 全部策略源码 | 用户 P0 commit hygiene, git 历史保留 |
| `~/quant-monitor-local/data/ashare_kline/` | 1950 只沪深 A 股 OHLCV | 数据池, 不动 |
| Flask 后端 PID 26225 :8000 | 监控面板后端运行 | 不动 |
| `~/goldcombo_real_backtest/v8_old_eatthebody_backup/v6_integration_backup/` | v8 集成快照 6 文件 | 历史回溯 |
| `~/goldcombo_real_backtest/v8final/` (新建) | 本次 V8final 工作目录 | 新建 |

## 监控面板重置状态

| 文件 | 状态 |
|---|---|
| `signals/goldcombo_2026-08-15.json` | ⏸️ 仍含 v6 5Y 数据 (备份在 `_v6_monitor_backup/`) — 等 T5 重写为 V8final 5Y |
| `config/strategies.json` | ⏸️ 仍含 v6 配置 (备份) — 等 T5 重写 |
| `index.html` | ⏸️ 仍含 v6 卡片 (备份) — 等 T5 重写 |

## 验证命令

```bash
$ ls /Users/junze/goldcombo_real_backtest/
T1_setup        T2_pool        T3_2y        T4_5y
v2              v3             v4           v6
v8_old_eatthebody_backup
v8final

$ ls /Users/junze/quant-monitor-local/strategies/goldcombo/ | grep _v6
goldcombo_strategy_ashare_v6.py       # 保留 (git 历史)

$ ls /Users/junze/quant-monitor-local/strategies/goldcombo/ | grep _v8
(空)                                  # 旧 v8 已删
```

## ⚠️ 未清理项 (discovered)

发现 brief 之外的遗留目录(用户原话"删除掉原先所有的旧数据"似包含但 brief 显式清单未列):
- `~/goldcombo_real_backtest/v2/` `v3/` `v4/` `v6/` (早期任务主目录, 各含 T0-T4 子目录)
- `~/goldcombo_real_backtest/T1_setup/` `T2_pool/` `T3_2y/` `T4_5y/` (更早期任务目录)

**未执行清理原因**: shell-hook 安全策略阻止后续递归 `rm -rf`, subagent 无权限在不询问的情况下强制绕过安全策略。这些目录不影响 V8final 5Y 真回测(任务 T4 走 `~/goldcombo_real_backtest/v8final/T4_5y/` 全新路径, 不依赖这些旧目录)。建议后续主 agent 在用户在场时确认是否一并清理。

## sha256 校验

- 用户 V8final 文件: `8d66c5841183bcd54861767490c1c7be42933c80663301a5a8eb0bfc92cda8c4` (8918B, RTF 包裹)
- 文件位置: `~/Downloads/股票筛选项目/自己写量化策略和脚本/混元三黄金组合优化V8final.py`

---

**T0 PASS** — 核心 brief 显式清单全部完成, 监控面板 v6 数据已备份等 T5 重写。