# Impeccable 接入与渐进式视觉升级

本分支只准备 Impeccable 的项目级集成，不修改网站页面、API、数据、策略逻辑或部署配置。

## 版本与来源

- 官方仓库： https://github.com/pbakaus/impeccable
- 本分支固定到官方提交：`d631a8827f99414d2b6daba4ef08b7f8701751d7`（上游提交说明为 Release 4.5.2）。
- 通过 Git Submodule 管理，便于复现及后续显式更新。

## 本项目的最高优先级约束

每次让 AI 修改界面前，必须先阅读 `PROJECT_RULES.md`。该文件明确优先于任何 Skill。

- 本接入工作不修改 `PROJECT_RULES.md`。
- 不修改策略 `.py`、回测或交易逻辑、Flask API、数据口径、收益计算、信号文件、历史累计数据。
- 不改变监控只读属性，不增加下单/成交操作。
- 公开版只使用仓库当前允许公开的数据；严禁把本机真实持仓、真实收益、私有信号或密钥写入公开分支。
- 先诊断和提出方案；未获确认前不要批量改版。
- 所有页面改动都放在单独分支，并通过 PR 审核；不直接向 `master` 推送。

## 在本地项目中完成接入

先确保本地工作区没有未提交的改动，再切换到本分支：

```bash
git fetch origin
git switch --track origin/chore/impeccable-integration
git submodule update --init --recursive
```

在项目根目录执行官方的链接命令。它会按所选开发工具生成相应的项目级 Skill 文件；下面覆盖几种常见环境。如果你只使用其中一种，也可以把列表缩减到实际使用的 Provider。

```bash
npx impeccable link --source=.impeccable --providers=claude,codex,cursor,github
```

其中 `github` 指 GitHub Copilot 的 Skill 适配，不是把仓库连接到 GitHub。接着重新加载/重启你的 AI 开发工具，并检查新生成的 Skill 文件：

```bash
git status --short
```

完成后，把生成的项目级 Skill 和配置文件一并提交到这个功能分支，不要提交本地运行数据、`.env` 或任何真实交易数据。

> 如果你的开发环境不支持上述 Provider，先不要猜测安装路径。查看官方安装说明并选择对应 Provider：https://github.com/pbakaus/impeccable#installation

## 诊断先行：第一轮不修改页面代码

在项目根目录运行 Impeccable 的初始化命令（不同开发工具的 Skill 调用符号可能略有区别）：

```text
/impeccable init
```

初始化后，先要求它只审查，不做代码修改：

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

也可以先对单个目标运行 `/impeccable audit index.html`。只在审阅并确认方案后，才对首页使用 `/impeccable polish index.html`；一轮只做一类视觉改动。

## 建议的渐进式实施顺序

1. **首页诊断**：记录现有桌面端与窄屏截图；列问题，不改代码。
2. **选定一个方向**：在保持深色监控产品可读性的前提下，先调整首页信息层级、间距和组件一致性。
3. **首页小步改版**：一次只做一个主题；对照截图检查策略卡、图表、状态标签和弹窗。
4. **回归验收**：验证策略卡详情弹窗、API 数据映射、刷新、键盘快捷键、图表和移动端溢出；不允许用假数据替代真实数据或改变数值口径。
5. **扩展至复盘页**：首页通过验收后再处理 `review.html`，统一视觉语言但保留各自的信息结构。
6. **PR 审核与部署**：确认差异仅涉及已批准的 UI 文件和样式后再合并；线上部署由原有发布流程控制。

## 更新 Impeccable

先检查上游变更与版本说明，再显式更新子模块。升级前后都应检查 Skill 内容与项目规则的优先级。

```bash
git submodule update --remote .impeccable
```
