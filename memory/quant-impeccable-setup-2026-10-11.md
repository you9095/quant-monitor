# 记忆：Impeccable 设计技能接入（2026-10-11）

- 用途：给 AI 量化面板做视觉升级。**唯一位置** `/Users/junze/.agents/skills/impeccable`（全机一份，禁重复副本）；引擎在 `/Users/junze/.impeccable/bin/0.1.14/impeccable`。
- 版本：技能锁定 commit `d631a8827f99414d2b6daba4ef08b7f8701751d7`（SKILL.md v4.5.2）；引擎 release `engine-v0.1.14` darwin-x64（18,783,784 B，sha256 dfa45703...，已校验一致）。`--version` 自报 `4.0.0`（与 tag 0.1.14 口径不同，文件无误）。
- 当前 AI 工具是 **Doubao（豆包）**，非 Hermes；官方不支持 Doubao，走通用 `.agents/skills` 手动集成，原生 hooks 可能不生效，靠手动 detect/audit。
- **网络通道（关键）**：raw.githubusercontent.com 被墙、github.com 主站被墙；**api.github.com 通、objects.githubusercontent.com 通**。下文件用 api tree/contents/blobs；下 release 资产用 api releases/assets/{id}（Accept: application/octet-stream → 302 到 objects），速度慢需 `curl -C -` 断点续传循环。
- 未认证 API 限额 60 次/小时：contents 目录列表不内联内容，别逐文件取；只对缺失文件 blobs。
- 不用 npx、不改 `~/.npmrc`（其 prefix 行会报错，本就绕过）。
- 用法：项目根跑 `/Users/junze/.agents/skills/impeccable/scripts/impeccable context`；新视觉走 init→new-work，微调走 polish/layout 等。不接券商、只改前端视觉，实盘/模拟口径不变。
- 本轮只完成安装+握手，未做实际视觉改版。
