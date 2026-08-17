# T2 · git commit 单一 commit 结论

**任务**: v4 → v6 单一 commit (不擅自拆 G/H)

## Commit 信息

- **Commit SHA**: `b38a856f8cccca408e0e30cbe3d97ff86111ee53`
- **短 SHA**: `b38a856`
- **作者**: subagent <subagent@local>
- **时间**: Sat Aug 15 13:32:33 2026 +0800
- **标题**: feat(goldcombo): v4 → v6 严控回撤去错杀版 (5% 硬止损回归 + 新增保本止损 + MACD 高位死叉回归)

## Commit 文件清单 (2 文件)

```
 strategies/goldcombo/goldcombo_strategy_ashare.py   |  23 +++-- (M)
 strategies/goldcombo/goldcombo_strategy_ashare_v6.py | 109 ++++++++ (A)
 2 files changed, 122 insertions(+), 10 deletions(-)
```

## Commit 内容要点

1. **alias 文件 `goldcombo_strategy_ashare.py`** 改 import 指向 v6:
   - `from strategies.goldcombo.goldcombo_strategy_ashare_v6 import GoldComboV6Strategy as GoldComboStrategy`
   - 文件头部 docstring 更新到 v6 (2026-08-15 版本管理 v6)
2. **新文件 `goldcombo_strategy_ashare_v6.py`**:
   - 类名 `GoldComboV6Strategy`
   - 含 5% 硬止损 (hard_sl=0.05) + 保本移动止损 (breakeven_pct=0.05, be_stop_pct=0.01) + CCI>120 + MACD 高位死叉
   - 彻底删除: ATR 自适应止损 / 阶梯移动止盈 / MA10 跌破 / 时间止损
   - 顶部注释含: 来源 sha256 + 解 RTF 时间 + 备份链 + v6 vs v4 差异

## v6 用户文件 sha256 (写入 commit message)

`3fc45cd06f57f654bfc78ed9ba82cf53b42c8290fb88fee49a6b37c3fe245726`

## Commit 链验证 (v1 → v2 → v3 → v4 → v6)

```
b38a856 feat(goldcombo): v4 → v6 严控回撤去错杀版 ...            [本次]
e91db0e feat(goldcombo): v3 → v4 灵活卖点版 ...                   [v3→v4]
57267e1 feat(goldcombo): v2 → v3 小资金严控版 ...                 [v2→v3]
da10a57 feat(goldcombo): v1 → v2 改良共振版 ...                   [v1→v2]
4964e52 feat(ashare): 重启 A 股 K 线下载 ...                      [pool fix]
```

✅ 5 个 commit 链完整,版本管理链路 (v1→v2→v3→v4→v6) 无断裂。

## 其他 untracked 文件 (本 commit 不动)

git status 显示以下 untracked 文件 (与本任务无关, 不擅自 add):
- `strategies/goldcombo/_ratchet_fast_runner.py`
- `strategies/goldcombo/_rebaseline_entry.py`
- `strategies/goldcombo/goldcombo_ratchet_ashare.py`
- `strategies/goldcombo/ratchet_backup_R*.json` (R10/R20/R30/R40/R50)
- `strategies/goldcombo/ratchet_baseline_ashare.json`
- `strategies/goldcombo/ratchet_final_baseline_ashare.json`
- `strategies/goldcombo/ratchet_log_ashare.json`

按指令"硬约束 8: 不能擅自拆 commit" + "硬约束 4: 不能丢 v1+v2+v3+v4 文件",这些文件已存在于 git 历史或待用户决定是否 commit,本 subagent 不擅自 add。

## T2 状态

**T2 (git commit): PASS** ✅

- Commit SHA: `b38a856f8cccca408e0e30cbe3d97ff86111ee53` ✅
- 文件清单: 2 文件 (1 修改 + 1 新增) ✅
- commit message 含 sha256 + 备份链 ✅
- v1→v2→v3→v4→v6 完整 commit 链 ✅