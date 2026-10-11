# Impeccable 接入与渐进式视觉升级

本分支准备 Impeccable 的项目级接入，不修改网站页面、API、策略逻辑、数据或部署配置。当前没有预先假定开发工具，因此需要先在本地按实际工具生成对应的 Skill/Hook 文件。

## 版本与来源

- 官方仓库：https://github.com/pbakaus/impeccable
- 本分支固定到上游提交：`d631a8827f99414d2b6daba4ef08b7f8701751d7`（上游提交说明为 Release 4.5.2）。
- 使用 Git Submodule 管理，方便团队复现并显式审查版本更新。
- 官方入门文档：https://impeccable.style/tutorials/getting-started/

## 本项目的最高优先级约束

每次让 AI 修改界面前，必须先阅读 `PROJECT_RULES.md`。该文件明确优先于任何 Skill。

- 本接入工作不修改 `PROJECT_RULES.md`。
- 不修改策略 `.py`、回测或交易逻辑、Flask API、数据口径、收益计算、信号文件、历史累计数据。
- 不改变监控只读属性，不增加下单/成交操作。
- 公开版只使用仓库当前允许公开的数据；严禁把本机真实持仓、真实收益、私有信号或密钥写入公开分支。
- 先诊断和提出方案；未获确认前不要批量改版。
- 所有页面改动都放在单独分支，并通过 PR 审核；不直接向 `master` 推送。

## 在本地项目中完成接入

先确保本地工作区没有未提交的改动，再获取并切换到接入分支：

```bash
git fetch origin
git switch --track origin/chore/impeccable-integration
git submodule update --init --recursive
```

确认你常用的 AI 编程工具，并且**只选择该工具对应的 Provider**。在项目根目录执行下面的一条命令（将示例中的 `codex` 替换成实际 Provider）：

```bash
npx impeccable link --source=.impeccable --providers=codex
```

常见 Provider 示例：
- Codex：`--providers=codex`
- Claude Code：`--providers=claude`
- Cursor：`--providers=cursor`
- GitHub Copilot：`--providers=github`
- Gemini CLI：`--providers=gemini`

`github` 指 GitHub Copilot 的 Skill 适配，不是用于连接 GitHub 仓库。支持的 Provider 及命令以官方安装说明为准：https://github.com/pbakaus/impeccable#installation

链接命令使用仓库内固定版本的 Impeccable 构建 Skill 文件。它**安装 Skill，不会安装设计 Hook**；不要在不理解本地自动化权限时手动补装 Hook。链接完成后，重新加载/重启开发工具并检查生成的项目文件：

```bash
git status --short
```

将需要共享的 Skill 配置提交到此功能分支。不要提交本地运行数据、`.env`、真实交易数据或机器专属配置。若工具生成了本地私有配置，先确认它已被正确忽略，再提交。

> 如果你不知道当前开发工具或 Provider，不要一次安装所有 Provider。先从你日常实际打开项目和执行 AI 编程任务的软件名称确认，再运行相应的一条命令。

## 初始化与诊断先行

在项目根目录运行初始化命令：

```text
/impeccable init
```

如果使用 Codex，请按官方说明使用 `$impeccable init`（或当前工具提示的等效调用方式）。初始化后，先要求它只审查，不做代码修改：

```text
请先读取 README.md 与 PROJECT_RULES.md，并检查 index.html、review.html 及相关前端资源。当前任务是视觉诊断，不是立即改版。

第一轮禁止修改任何应用代码、HTML、CSS、JS、API、数据或部署文件。请输出：
1. 当前设计系统的总结及值得保留的部分；
2. 按影响和实施风险排序的视觉问题；
3. 三种差异明显但符合量化监控产品定位的视觉方向，不预先假定必须采用某一种；
4. 每种方向在信息层级、数字可读性、图表、配色、排版、间距、移动端和无障碍方面的改进建议；
5. 推荐的最小改动试点及验收清单。

收益率、盈亏、现金、持仓、数据期、策略状态、回测/实盘口径和颜色语义都属于产品信息，不允许仅为视觉效果而更改其含义或来源。诊断完成后停下，等待用户审阅。
```

可先用 `/impeccable audit index.html` 诊断首页（Codex 用 `$impeccable audit index.html`）。只有审阅并确认方案后，才对首页使用 `/impeccable polish index.html`（Codex 用 `$impeccable polish index.html`）；每轮只做一类视觉改动。

## 渐进式实施顺序

1. **首页诊断**：记录现有桌面端与窄屏截图；只列问题，不改代码。
2. **选择方向**：围绕量化监控的可信度与数字可读性比较方案，不预设必须换成某个潮流风格。
3. **首页小步改版**：一次只做一个主题；对照截图检查策略卡、图表、状态标签和弹窗。
4. **回归验收**：验证策略卡详情弹窗、API 数据映射、刷新、键盘快捷键、图表和移动端溢出；不允许用假数据替代真实数据或改变数值口径。
5. **扩展至复盘页**：首页通过验收后再处理 `review.html`，统一视觉语言但保留各自的信息结构。
6. **PR 审核与部署**：只合并已批准且通过测试的 UI 变更；线上部署仍走原有发布流程。

## 更新 Impeccable

先查看上游变更与版本说明，再显式更新子模块、重新链接所需 Provider，并逐项审查产生的变化：

```bash
git submodule update --remote .impeccable
npx impeccable link --source=.impeccable --providers=codex
```

把上面命令里的 `codex` 改成你实际使用的 Provider。更新后要检查 Skill 内容和本项目规则的优先级。官方文档：https://impeccable.style/tutorials/getting-started/
