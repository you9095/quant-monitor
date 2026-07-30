# 量化监控面板 — 版本管理规则 v1.0

> 生效起点：2026-07-30（commit `1d4d862` 之后）
> 适用项目：`quant-monitor-local`（线上：https://you9095.github.io/quant-monitor/）
> 文档等级：**P0 硬约束**（违反 = 视为破坏性变更，必须经用户授权）

---

## 1. 规则适用范围

本规则约束 `quant-monitor-local` 仓库的所有变更版本标识，包括：
- 前端（`index.html` / `review.html` / `assets/*.js`）
- 后端 API（`api/real_data_server_v2.py` 等）
- 数据层（`signals/` / `config/strategies.json` / `assets/data_v2.js`）
- 脚本层（`scripts/bridge_*.py` / `scripts/audit_*.sh`）
- 文档（`README.md` / `ARCHITECTURE.md` / `POSTMORTEM_*.md`）

**不适用**：单文件 ad-hoc 验证脚本（`hermes-verify-*.py` 临时调试用，不入版本）。

---

## 2. 版本号体系 — 双轨制

项目同时存在 **代码版本** 和 **数据期版本** 两条线，前者用 SemVer，后者用日期 + 棘轮轮次。

### 2.1 代码版本（SemVer 简化版：`X.Y.Z`）

| 位 | 名称 | 何时递增 | 示例 |
|---|---|---|---|
| **X（主版本）** | 重大架构变更 | 前端布局重构 / 后端 API schema 破坏性变更 / 上线策略数从 N→M | 1→2（五策略上线） |
| **Y（次版本）** | 功能性新增 | 新增策略类型 / 新增 API 端点 / 新增复盘维度 | 0→1（信号日期过期自动隐藏） |
| **Z（修订号）** | 修复 / 优化 | bugfix / 文案优化 / 性能 / 数据口径修正 | 1→2→3 |

**初始版本**：`v1.0.0`（追溯标记于 commit `b4224d7`，2026-06-08，三策略上线）。

### 2.2 数据期版本（`YYYY-MM` 或 `ratchet-R{NN}`）

不与代码版本绑定，独立维护：

- **数据期**：`YYYY-MM`，代表回测/验证所用的数据时间窗口（如 `2024-06~2026-06` = 2Y）
- **棘轮轮次**：`R{NN}`，单策略每完成一轮棘轮迭代 +1（如 `qixing` 当前 `R120`）
- **数据期版本号**：`{策略}-{R号}-{数据期}`，如 `qixing-R120-2024-06_2026-06`

**写入位置**：
- 策略信号文件 `signals/{strategy}_*.json` 的 `version` 字段
- API 返回的 `strategies[].version` 字段
- `config/strategies.json` 的 `version` 字段

### 2.3 双轨关系

代码版本变更**不一定**触发数据期版本变更（如纯前端 bugfix）。数据期版本变更**可能**触发代码版本 `Y` 位递增（如新增棘轮监控维度）。

---

## 3. 标签（Tag）管理

### 3.1 Tag 命名规范

| 类型 | 格式 | 示例 | 推送 |
|---|---|---|---|
| **稳定发布版** | `vX.Y.Z` | `v1.0.0`、`v1.2.3` | 推到 origin |
| **预发布版** | `vX.Y.Z-rc.{N}` | `v1.2.0-rc.1` | 推到 origin |
| **数据期快照** | `data-{YYYY-MM}-{描述}` | `data-2026-06-ratchet-baseline` | 推到 origin |
| **关键修复锚点** | `fix-{简短描述}-{日期}` | `fix-five-strategy-launch-20260616` | 推到 origin |

**禁止**：纯数字 tag、含空格 tag、未带前缀的临时 tag。

### 3.2 Tag 触发时机（强制打 tag 的节点）

| 触发条件 | Tag 类型 | 谁来打 |
|---|---|---|
| 首次上线 GitHub Pages | `v1.0.0` | 主 agent 在 deploy 后立即打 |
| 每次上线后通过 `audit_daily.sh` 的 P0/P1 修复 | `vX.Y.Z`（Z+1） | 主 agent 在 commit 后立即打 |
| 棘轮迭代完成（新 R 号发布） | `data-{YYYY-MM}-{策略}-R{NN}` | 主 agent 在 commit 后立即打 |
| 重大事故复盘完成 | `fix-{描述}-{日期}` | 主 agent 在 POSTMORTEM commit 后立即打 |
| 用户明确说"发布 X 版本" | 按用户指定格式 | 主 agent |

### 3.3 Tag 操作铁律

- **每个 tag 必须有附注**：`git tag -a vX.Y.Z -m "一句话描述本次变更"`
- **tag 必须推到 origin**：`git push origin vX.Y.Z`（不可仅本地）
- **严禁 force push tag 后删除**——除非用户明确授权（破坏性变更，必须走 §6 流程）
- **tag 命名禁止重名**——若需重打，必须先删除再重打，但删除前必须 `git tag -l` 列出所有现存 tag 报用户

### 3.4 Tag 与 commit 的关系

**一个 tag = 一个 commit 锚点**，严禁一个 tag 跨多个 commit。
**严禁"tag 后追加 commit"**——若发现 tag 后有新 commit 属于该版本，必须删除旧 tag 并在新 HEAD 重打。

---

## 4. CHANGELOG 规范

### 4.1 文件位置

仓库根目录：`/Users/junze/quant-monitor-local/CHANGELOG.md`

### 4.2 格式（Keep a Changelog v1.1 + SemVer）

```markdown
# Changelog

所有项目的显著变更都会记录于此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added（新增功能）
- 待写

### Changed（变更）
- 待写

### Fixed（修复）
- 待写

### Removed（移除）
- 待写

## [X.Y.Z] - YYYY-MM-DD

### Added
- 具体描述（#issue/PR-id）

### Changed
- ...

### Fixed
- ...

### Removed
- ...
```

### 4.3 写入时机（强制）

| 触发 | 谁来写 | 写入什么 |
|---|---|---|
| 任何 `vX.Y.Z` tag 创建前 | 主 agent | 把 `[Unreleased]` 内容归入新版本 + 加新 `[Unreleased]` |
| 任何 commit 涉及用户可感知变更 | 主 agent（commit 后立即） | 在 `[Unreleased]` 下追加条目 |
| 棘轮 R 号变化 | 主 agent | 在 `[Unreleased]` 加 `data-{策略}-R{NN}` 条目 |

**CHANGELOG 写入必须在 commit 之前或同 commit 内**，禁止 commit 后再补。

### 4.4 类别划分

每条变更必须归入以下 4 类之一（不可省略、不可自创第 5 类）：

| 类别 | 用于 |
|---|---|
| **Added** | 新增功能、新增策略、新增 API 端点 |
| **Changed** | 既有功能变更（如调整阈值、改默认参数） |
| **Fixed** | bug 修复 |
| **Removed** | 删除功能、删除 API 端点、删除区段（如 ec5d944 删 4 区段） |

**严禁**：用 "Updated" / "Improved" / "Optimized" 等模糊词——必须按事实归入 4 类。

---

## 5. Commit 规范

### 5.1 Conventional Commits 强制化

格式：`<type>(<scope>): <subject>`

| type | 用于 |
|---|---|
| `feat` | 新功能 |
| `fix` | bug 修复 |
| `refactor` | 重构（无功能变更） |
| `docs` | 仅文档 |
| `style` | 仅格式（无逻辑变更） |
| `test` | 仅测试 |
| `chore` | 构建/工具/依赖 |
| `perf` | 性能 |
| `revert` | 回滚 |

**scope** 可选，常用值：`frontend` / `backend` / `data` / `scripts` / `docs` / `config`

**subject** 要求：
- 中文或英文均可，但**项目内统一一种**（推荐中文，符合用户偏好）
- ≤ 50 字符
- 不加句号
- 用动词开头（"新增" / "修复" / "删除" / "同步"）

**body**（可选）：
- 说明"为什么"而非"是什么"
- 与 subject 间空一行

### 5.2 Breaking Change 标记

任何破坏性变更必须在 footer 加：

```
BREAKING CHANGE: <一句话说明>
```

并自动触发：
1. 代码版本 **X 位 +1**、Y/Z 归零
2. CHANGELOG 的 `[X.Y.Z]` 顶部加 `### ⚠️ BREAKING CHANGES` 区
3. 标 `!` 前缀：`feat(api)!: 重写 dashboard overview 返回 schema`

### 5.3 反模式（commit 写法禁止清单）

| ❌ 错误 | ✅ 正确 |
|---|---|
| `update` | `feat` / `fix` / `refactor` |
| `修复 bug` | `fix: 修复 labelMap 缺 lightning 字串` |
| `一些改动` | `refactor(frontend): 删除 4 个非核心区段` |
| `feat: 新增功能`（subject 太泛） | `feat(frontend): 新增 5 策略颜色一致性校验` |
| 多个无关变更合一个 commit | 拆成多个原子 commit |

---

## 6. 破坏性变更流程（P0 触发用户授权）

下列任一情况必须走"双确认 P0 流程"（参考 user profile §破坏性操作双确认）：

1. **删除 tag**（已推 origin 的 tag）
2. **删除分支**（含已合并的 master 之外的分支）
3. **删除 git 历史 commit**（`git rebase -i` / `git reset --hard` 等）
4. **强制 push**（`git push --force` / `git push --force-with-lease`）
5. **大段代码删除**（单 commit 删除 ≥100 行非注释代码）
6. **删除功能区段**（如 ec5d944 类删除 HTML 区段）

### 6.1 强制 4 步流程

```
[Step 1] 列清单
    → 列出待删除/变更的对象全路径、commit hash、行数、影响面
[Step 2] 双确认
    → 用户口头确认 + 书面授权（消息内复述清单）
[Step 3] 备份
    → 执行前 `git tag backup-before-{operation}-{ts}` 打本地备份 tag
[Step 4] 执行 + 验证
    → 每步独立命令独立 verify，禁止 `rm -rf`、禁止 pipeline
```

### 6.2 反面案例（已被 agent 踩过的坑）

- **2026-07-29 commit `6647cf2`**：agent 自主删除 4 区段（505 行）→ 用户当场反对 → 同日 `aa42184` revert → 后由用户明确授权 `ec5d944` 重新执行。
- **教训**：任何"看似非核心"的删除都要走 §6 流程。

---

## 7. 主 agent 工作流（自动执行）

### 7.1 每次 commit 前自检清单

```
□ 这是用户明确要求的变更吗？（避免 agent 自主越权）
□ commit message 符合 Conventional Commits 吗？
□ 如涉及用户可感知变更 → 已先写 CHANGELOG [Unreleased]？
□ 如是删除/重构/重大变更 → 已走 §6 双确认？
□ 如达到打 tag 节点（§3.2）→ 准备 commit 后立即打 tag？
□ 是否触发破坏性变更 → BREAKING CHANGE footer + X+1？
```

### 7.2 commit 后立即执行（不可跳过）

```bash
# 1. 推 master
git push origin master

# 2. 判定是否打 tag
#    触发条件见 §3.2

# 3. 如打 tag：
git tag -a vX.Y.Z -m "{subject 摘要}"
git push origin vX.Y.Z

# 4. 更新 CHANGELOG（如果还没在 commit 前写）
#    把 [Unreleased] 内容归入新 [X.Y.Z]，写日期，加新 [Unreleased]
git add CHANGELOG.md
git commit -m "docs(changelog): 发布 vX.Y.Z"
git push origin master
```

### 7.3 棘轮迭代触发的版本动作

```
新 R 号发布时（如 qixing R120 → R121）：
1. 更新 config/strategies.json 的 version 字段
2. 更新 api/real_data_server_v2.py 的版本映射（如果有）
3. commit: refactor(config): qxing 棘轮 R120 → R121
4. 打 tag: data-2026-07-qixing-R121
5. CHANGELOG [Unreleased] 追加条目
```

---

## 8. 用户交互协议

### 8.1 用户可用的版本查询命令

| 用户原话 | 主 agent 行为 |
|---|---|
| "现在线上是什么版本" | `git describe --tags --always` + `git tag -l \| tail -10` + 报最近 tag + 当前 HEAD |
| "上一个发布版" | `git tag -l 'v*' --sort=-v:refname \| head -1` |
| "v1.2.0 改了什么" | `git log v1.1.0..v1.2.0 --oneline` + 报 CHANGELOG 对应段落 |
| "回滚到 v1.1.0" | **禁止直接执行**，走 §6 双确认 + 出回滚方案 |
| "把这次改动发布成 v1.2.0" | 走 §7.2 全流程，commit 后立即打 tag |

### 8.2 主动汇报节点

主 agent 在以下节点必须主动告知用户（不静默）：

1. 打 tag 后（"已发布 v1.2.0，含 3 个 fix"）
2. 检测到 `git tag -l` 出现同名冲突（"tag 重名警告"）
3. CHANGELOG 滞后 ≥3 个 commit 未更新（"CHANGELOG 提醒"）
4. 发现 commit message 不符合 Conventional Commits（"commit 格式警告"）

---

## 9. 版本管理与现有体系的关系

| 既有机制 | 与本规则关系 |
|---|---|
| `git log` commit 历史 | 仍是追溯基础，CHANGELOG 是其结构化摘要 |
| `logs/工作日志_*.md` | 工作日志是 1-shot 临时记录，CHANGELOG 是累积版本记录——**两者互补**，不互替 |
| `POSTMORTEM_*.md` | 重大事故复盘文档，必须在 tag `fix-{描述}-{日期}` 创建同日完成 |
| `outputs/` 实验产出 | 不入版本管理（一次性实验产物） |
| `signals/` 策略信号文件 | 文件名含日期已是隐式版本，配合 `version` 字段双轨 |

---

## 10. 反面教材沉淀

### 10.1 2026-07-30 之前：完全无版本管理

- 21 个 commit，0 个 tag，0 个 CHANGELOG
- 用户问"线上什么版本"只能报 commit hash（如 `1d4d862`）
- 无法快速回答"v1.2.0 改了什么"
- 删除类变更（6647cf2）由 agent 自主判断造成 revert 事故

### 10.2 改进预期

- 7 天内：所有 commit 走 Conventional Commits（渐进，已有 commit 不强求改）
- 14 天内：补齐历史 tag（从 b4224d7 起，按 §3.2 节点回溯打 5-7 个 tag）
- 30 天内：CHANGELOG 持续维护，无滞后 ≥3 commit

---

## 11. 规则生效与修订

- **生效日**：2026-07-30（commit `1d4d862` 之后下一个 commit 起强制）
- **历史 commit 不追溯改写**（保护 git 历史真实性）
- **修订本规则**：必须经用户授权 + 更新版本号到本文件头（"规则"自身也走 SemVer：`v1.0` → `v1.1`）
- **撤销任何条款**：走 §6 双确认

---

## 附：30 天落地 checklist

```
□ Day 1-2：  本规则文档 commit + 打 tag `v1.0.0-rules`
□ Day 3-7：  历史 tag 回溯（从 b4224d7 起 5-7 个关键节点）
□ Day 7：    创建 CHANGELOG.md 初始版本，回填 21 commit
□ Day 14：   audit_daily.sh 集成 §7.2 自动 commit-tag-CHANGELOG 流程
□ Day 30：   复盘 30 天执行情况，决定是否升级到 v1.1
```