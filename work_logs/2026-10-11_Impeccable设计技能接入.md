# 2026-10-11 Impeccable 设计技能接入（Mac 侧，为面板视觉升级做准备）

## 一、目的与边界
- 引入 Impeccable（pbakaus/impeccable）：给 AI 编程助手用的设计技能（1 skill + 24 命令 + 浏览器实时迭代 + 59 条确定性检测），用于逐步升级 AI 量化面板的视觉设计。
- **唯一存放位置**：`/Users/junze/.agents/skills/impeccable`（全机只此一份，无重复副本）。
- 硬约束（用户铁律）：不检出 `chore/impeccable-integration` 分支、不 submodule、不克隆/长期保留整仓、不用 npx、不改 `~/.npmrc`、不碰量化项目代码/Git/配置、不接券商、不改网站与实盘数据。

## 二、关键事实（环境）
- 当前实际 AI 工具是 **Doubao（豆包）**，不是 Hermes——机器虽装 `~/.hermes`，但本轮会话由 Doubao 执行。Impeccable 官方一键支持列表无 Doubao，走通用 `.agents/skills/impeccable` 手动集成。
- 项目根 `/Users/junze/quant-monitor-local`（由监听 8000 端口进程的 cwd 硬定位），当前在 master，远程 `git@github.com:you9095/quant-monitor.git`。
- 本机 Intel x86_64、macOS 13.7.8；磁盘紧张（可用约 9 GB）。
- `~/.npmrc` 第1行 `prefix=~/npm-global` 会让 Doubao 自带 npm 报 "prefix cannot be changed from project config"——**本次不改它**，也不用 npx。

## 三、网络通道结论（重要教训）
- `raw.githubusercontent.com`：**被墙**（超时、0 字节）。
- `github.com` 主站：**被墙**（release 下载拿不到 302，http=000）。
- `api.github.com`：**通**（tree/release/asset 元数据都走这里）。
- `objects.githubusercontent.com`：**通**（根路径返回 404 = 可达）。
- 可行路线：
  - 技能文件 → `api.github.com` 的 git trees（取清单）+ contents 列目录 + 缺失文件走 git blobs（按 sha 取 base64）。
  - 引擎二进制 → `api.github.com` releases/assets/{id} 带 `Accept: application/octet-stream`，由 api 子域 302 到 objects 签名直链；**速度慢（约 35KB/s）需断点续传 `-C -` + 循环刷新签名直链**。
- 未认证 API 限额 **60 次/小时**：contents"目录列表"不内联文件内容，逐文件取会超限；做法是目录列表只取路径，只对缺失文件 blobs，控制在个位数请求。

## 四、部署结果（全部校验通过）
- 技能：锁定 commit `d631a8827f99414d2b6daba4ef08b7f8701751d7`，62 个文件 / 2.2 MB（2,216,993 B）；每个文件做"字节数 + Git blob SHA1"双校验（下载时一次、独立代码复核一次），全部一致；`scripts/impeccable` 已加可执行位。
- 引擎：`engine-v0.1.14` / `impeccable-darwin-x64`，18,783,784 字节；SHA-256 `dfa4570309939f49615a441baa9c73f1c2d339bf07494517a6c6eb28aa0f5`，与官方 release asset digest 完全一致。
- 引擎安装位置：`/Users/junze/.impeccable/bin/0.1.14/impeccable`（18 MB，-rwxr-xr-x，无 quarantine）。
- 版本握手：引擎本体与技能 launcher 均返回 `4.0.0`。**注意**：标签是 0.1.14，但 `--version` 自报 4.0.0，属上游版本号口径差异，文件来源/哈希无误。
- 临时下载文件已清理（18 MB），磁盘未留残片。

## 五、怎么用（下次开始视觉升级时）
1. 在项目根 `/Users/junze/quant-monitor-local` 跑：`/Users/junze/.agents/skills/impeccable/scripts/impeccable context`（一次会话一次；引擎已就位，无需 Node、不会再下载）。
2. 按 SKILL.md 路由：新视觉世界走 init→new-work；已有界面微调走对应命令（polish/layout/colorize/typeset…）。
3. 不接任何券商账号；只改前端视觉，实盘/模拟数据口径不变。

## 六、待办 / 风险
- 尚未真正跑一次视觉升级（本轮只做安装与握手）。
- Doubao 非官方 harness，Impeccable 的原生 hooks（编辑后自动跑检测器）可能不生效；先靠手动 `detect`/`audit` 验证。
- Windows 端实盘机暂不需要此技能（视觉设计在 Mac 做）。
