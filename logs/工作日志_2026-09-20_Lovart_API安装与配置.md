# 工作日志 · 2026-09-20 · Lovart API 本机安装与 4 个核心 API 对比

## 任务背景
用户要求：本机安装 Lovart 插件，从 4 个 API 中找到最合适的那个。

## 执行过程

### 1. 官方域名澄清
- ❌ `lovart.art` = 中文设计师版（画布编辑器），无 API
- ✅ `lovart.ai` = 国际开发者版，有完整 API 文档、SDK、Key 管理

### 2. 本机已安装包（验证通过）
| 包名 | 版本 | 类型 | 状态 |
|------|------|------|------|
| `lovart` | 1.2.5 | 官方 CLI | ✅ 语法检查通过、帮助完整、含 8 子命令 |
| `@lovart-open/canvas-mcp` | 1.2.5 | MCP 服务器 | ✅ 语法检查通过、可接入 Cursor/Claude Code |

### 3. 4 个核心 API 完整对比（基于官网 + CLI 源码验证）

| # | API 名称 | CLI 命令 | 核心能力 | 适用场景 | 推荐模型 |
|---|----------|----------|----------|----------|----------|
| 1 | **AI Design API** | `text2image` / `image2image` | 文生图、图生图、品牌感知、Touch Edit 多轮修改 | 海报、Banner、电商主图、Logo | GPT Image 2、FLUX、Nano Banana Pro |
| 2 | **AI Video Editor API** | `videoedit` / `remove_background` | 视频去背、物体修复、调色、格式转换、批量处理 | 短视频后期、商品视频去背、多规格导出 | Seedance 2、Veo 3 |
| 3 | **AI Text-to-Video API** | `text2video` / `frames2video` / `multiref2video` | 文生视频、首尾帧生视频、多参考帧、长视频拼接 | 产品演示、广告片、动画短片 | Seedance 2、Kling、Veo 3、Minimax H3 |
| 4 | **AI Content Format Converter** | `asset_upload` + 智能重排 | 一键生成 20+ 平台规格、焦点保持、文字区域保护 | 全渠道投放、社媒矩阵、广告网络适配 | 内部智能重排引擎 |

### 4. 选型决策矩阵（无单一最优，按任务选）

| 你的任务 | 直接用这条命令 |
|----------|----------------|
| 需要带品牌风格的海报/配图 | `lovart text2image --prompt "..." --brand-kit-id "bk_xxx"` |
| 有参考图，想改风格/换元素 | `lovart image2image --prompt "..." --reference ./ref.png` |
| 需要 5-30 秒产品演示/广告视频 | `lovart text2video --prompt "..." --ratio 16:9 --duration 10` |
| 已有视频素材，要去背/换背景/调色 | `lovart videoedit --prompt "remove background" --reference-video in.mp4` |
| 有一张主视觉，要秒出 20+ 平台规格 | `lovart asset_upload --asset-type image --source ./hero.png` |

### 5. 当前阻塞点
- **缺少 API Key**：所有 4 个 API 调用均需有效 Key
- 获取地址：https://www.lovart.ai → Developer → API Keys → Generate
- 配置方式：`export LOVART_API_KEY="***"` 或 `lovart auth login`

### 6. 用户测试命令（待 Key 后执行）
```bash
lovart text2image \
  --prompt "院长穿蜜雪冰城红白制服，手持雪王周边，站在蜜雪冰城门店前，红白配色，扁平插画风，商业海报级，干净背景" \
  --ratio 3:4 \
  --resolution-type 2K \
  --model-version "GPT Image 2"
```

## 遗留/待办
- [ ] 用户获取 API Key 后验证端到端出图
- [ ] 如需 MCP 集成，配置 `~/.cursor/mcp.json` 或 `claude_desktop_config.json`
- [ ] 实测 4 个 API 的实际生成质量、延迟、成本对比

## 关键文件路径
- CLI 入口：`/Users/junze/npm-global/bin/lovart` → `/Users/junze/npm-global/lib/node_modules/lovart/src/index.js`
- MCP 入口：`/Users/junze/npm-global/lib/node_modules/@lovart-open/canvas-mcp/dist/index.js`
- 配置文件（登录后生成）：`~/.config/lovart/config.json`

