# Impeccable 设计技能（Mac 侧视觉升级工具）

> 接入日期：2026-10-11　｜　用途：逐步升级 AI 量化监控面板的前端视觉

## 它是什么
Impeccable 是给 AI 编程助手用的"设计语言/技能"：1 个 SKILL.md + 24 个命令（polish、critique、audit、layout、colorize、typeset、live 等）+ 59 条前端反模式检测规则。目标是摆脱"千篇一律的 SaaS 模板脸"（Inter 字体、紫蓝渐变、卡片套卡片、灰字彩底）。

## 装在哪（只此一份）
- 技能：`/Users/junze/.agents/skills/impeccable`（62 文件 / 2.2 MB）
- 引擎：`/Users/junze/.impeccable/bin/0.1.14/impeccable`（18 MB，已校验 SHA-256）
- 不用 Node、不用 npx；首次运行引擎已就位，无需再下载。

## 怎么启动
在项目根 `/Users/junze/quant-monitor-local` 执行：
```
/Users/junze/.agents/skills/impeccable/scripts/impeccable context
```
- 新页面/换风格：init → new-work
- 在现有面板上打磨：polish / layout / colorize / typeset 等
- 体检：audit / critique

## 边界（红线）
- 只改前端视觉，**不接任何券商真实账号**；实盘模拟、本机撮合的口径不变。
- Windows 实盘机不需要装这个（设计在 Mac 做，代码仍走 GitHub 中转）。
- Doubao（豆包）非官方支持工具，原生"改完自动检测"钩子可能不生效，靠手动跑 detect/audit。

## 网络坑（下次重装别再踩）
- `raw.githubusercontent.com`、`github.com` 主站在本机网络被墙；
- 能用的是 `api.github.com` 和 `objects.githubusercontent.com`；
- 下载走 api 的 tree/contents/blobs，release 大文件走 api releases/assets（octet-stream）+ 断点续传。
