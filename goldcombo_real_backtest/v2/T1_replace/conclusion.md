# T1 代码替换 + git commit — 结论

## 文件替换清单

| 文件 | 操作 | sha256 (落位后) |
|------|------|------------------|
| strategies/goldcombo/goldcombo_strategy_ashare_v2.py | 新建 | a16653578143b69a11d0f66e17697fcc19a53ee93611dbe78432fa8475bcaaa1 |
| strategies/goldcombo/goldcombo_strategy_ashare.py | 修改 (顶部加 v2 import 别名) | 见 git diff commit da10a574 |

## 替换策略 (保守做法)

- v1 `goldcombo_strategy_ashare.py` 保留文件 (改 import 指向 v2)
  - 顶部新增 `from strategies.goldcombo.goldcombo_strategy_ashare_v2 import GoldComboRelaxedStrategy as GoldComboStrategy`
  - 这样旧 import 路径 `from goldcombo_strategy_ashare import GoldComboStrategy` 不需要改
  - 类名实际指向 v2 的 `GoldComboRelaxedStrategy` (Gated Voting)
- v2 真实内容在独立文件 `goldcombo_strategy_ashare_v2.py`
- v1 备份完整保留: `~/goldcombo_real_backtest/v1_backup/` (5 个文件)

## git commit

- SHA: `da10a574b5296fcc1097bcf8b19c29b116659773`
- 短 SHA: `da10a574`
- message: `feat(goldcombo): v1 → v2 改良共振版 (Gated Voting C3+vote≥2)`
- 改动: 2 files changed, 426 insertions(+)
  - create mode 100644 strategies/goldcombo/goldcombo_strategy_ashare.py
  - create mode 100644 strategies/goldcombo/goldcombo_strategy_ashare_v2.py
- amend 原因: 第一次 commit 中 v1 alias 用相对 import (`from goldcombo_strategy_ashare_v2`) 在 sys.path 下找不到 v2, 改成绝对 import (`from strategies.goldcombo.goldcombo_strategy_ashare_v2`) 后 amend 进同一 commit

## 不动的东西 (符合硬约束)

- `goldcombo_strategy.py` (ETF 池版) 未动
- 所有 `ratchet_*.json` 未动
- `monitor_*.html` 未动
- `api/real_data_server_v2.py` 等其他 M 文件未 stage

T1 状态: **PASS**
