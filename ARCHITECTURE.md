# 三策略监控面板 · 架构设计文档 V2.0

## 一、核心设计原则

### 1. 策略即配置
- 策略不是硬编码，而是从 `config/strategies.json` 动态加载
- 增加/删除/修改策略只需改配置文件，无需改代码
- 前端通过 `/api/v1/strategies` 获取策略列表，自适应渲染

### 2. 信号即文件
- 每日持仓和交易动作从 `signals/` 目录的 JSON 文件读取
- 文件名格式：`{strategy_id}_{YYYY-MM-DD}.json`
- 策略迭代后只需更新信号文件，可视化层无感知

### 3. 接口向后兼容
- 所有 API 路由支持动态策略 ID（`/<sid>/positions`）
- 新增策略自动获得完整 API 支持
- 404 处理：策略不存在时返回标准错误格式

---

## 二、文件结构

```
项目根目录/
├── config/
│   └── strategies.json          # 策略配置文件（热加载）
├── signals/
│   ├── qixing_2026-06-08.json   # 七星策略今日信号
│   ├── r32_2026-06-08.json      # R32策略今日信号
│   └── zhuidian_2026-06-08.json # 追电策略今日信号
├── api/
│   ├── real_data_server_v2.py   # Flask后端（动态策略版）
│   └── venv/                    # Python虚拟环境
├── assets/
│   ├── data_v2.js               # 前端数据层（动态策略版）
│   └── data.js                  # 旧版（保留兼容）
├── index.html                   # 主监控面板
├── review.html                  # 盘后复盘页面
└── ARCHITECTURE.md              # 本文档
```

---

## 三、策略配置文件格式

```json
{
  "qixing": {
    "name": "七星策略",
    "color": "#3b82f6",
    "initial_capital": 10000,
    "description": "创业板动量策略",
    "version": "1.7.2"
  },
  "r32": {
    "name": "三驾马车R32",
    "color": "#10b981",
    "initial_capital": 10000,
    "description": "行业轮动棘轮策略",
    "version": "R32"
  }
}
```

### 关键字段
| 字段 | 说明 | 是否必须 |
|------|------|----------|
| name | 策略显示名称 | 是 |
| color | 图表/卡片颜色 | 是 |
| initial_capital | 初始本金 | 否（默认10000） |
| description | 策略描述 | 否 |
| version | 策略版本号 | 否 |

---

## 四、信号文件格式

```json
{
  "date": "2026-06-08",
  "strategy_id": "qixing",
  "positions": [
    {"code": "159915", "name": "创业板ETF", "qty": 2510, "cost": 3.977}
  ],
  "action": {
    "action": "BUY",
    "target": "159915",
    "detail": "买入 2,510 股 · 成本 ¥3.977",
    "trades": [
      {"time": "09:30:15", "action": "buy", "code": "159915", "qty": 2510, "price": 3.977, "amount": 9982.27}
    ]
  }
}
```

---

## 五、API 路由清单

### 全局路由
| 路由 | 说明 |
|------|------|
| `GET /api/v1/strategies` | 获取所有策略配置 |
| `GET /api/v1/dashboard/overview` | 仪表盘概览（所有策略） |
| `GET /api/v1/dashboard/nav_curves` | 所有策略净值曲线 |
| `GET /api/v1/health` | 健康检查 |

### 策略级路由（`<sid>` 为策略ID）
| 路由 | 说明 |
|------|------|
| `GET /api/v1/<sid>/nav_curve` | 单策略净值曲线 |
| `GET /api/v1/<sid>/positions` | 单策略持仓 |
| `GET /api/v1/<sid>/risk_metrics` | 单策略风险指标 |
| `GET /api/v1/<sid>/today_actions` | 单策略今日交易 |
| `GET /api/v1/<sid>/status` | 单策略状态 |

---

## 六、棘轮迭代的影响分析

### 场景1：策略参数调整（如 R32 → R33）
**影响范围：** 无
**原因：** 策略ID不变（仍为 `r32`），信号文件格式不变
**操作：** 只需更新 `signals/r32_*.json` 中的持仓数据

### 场景2：策略版本重命名（如 R32 → R41）
**影响范围：** 配置文件 + 信号文件名
**操作：**
1. `config/strategies.json` 中修改键名 `r32` → `r41`
2. `signals/` 中文件重命名 `r32_*.json` → `r41_*.json`
3. 前端自动适配，无需修改

### 场景3：新增策略（如第4策略 "dongfang"）
**影响范围：** 仅新增配置和信号文件
**操作：**
1. `config/strategies.json` 新增 `"dongfang": {...}`
2. 创建 `signals/dongfang_2026-06-08.json`
3. 后端自动识别，前端自动渲染

### 场景4：删除策略
**影响范围：** 配置文件 + 信号文件
**操作：**
1. 从 `config/strategies.json` 删除对应键
2. 可选：删除 `signals/` 下对应文件
3. 前端自动减少卡片数量

---

## 七、增加第4、第5个策略的操作步骤

### 步骤1：修改配置文件
编辑 `config/strategies.json`，新增策略：

```json
{
  "qixing": { ... },
  "r32": { ... },
  "zhuidian": { ... },
  "dongfang": {
    "name": "东方策略",
    "color": "#ef4444",
    "initial_capital": 10000,
    "description": "东方趋势跟踪"
  }
}
```

### 步骤2：创建信号文件
创建 `signals/dongfang_2026-06-08.json`：

```json
{
  "date": "2026-06-08",
  "strategy_id": "dongfang",
  "positions": [...],
  "action": {...}
}
```

### 步骤3：重启后端（或等待热加载）
```bash
cd api && source venv/bin/activate && python real_data_server_v2.py
```

### 步骤4：验证
- 访问 `http://localhost:8000/api/v1/strategies` 确认新策略出现
- 打开面板确认新卡片渲染正常
- 图表自动增加新曲线

---

## 八、前端自适应机制

### 策略卡片渲染
- 前端调用 `/api/v1/strategies` 获取策略列表
- 根据返回数量动态生成卡片（3个→4个→5个）
- 颜色从配置读取，无需硬编码

### 图表自适应
- 净值曲线接口返回 `curves: {sid1: {...}, sid2: {...}}`
- Chart.js 数据集根据 `Object.keys(curves)` 动态构建
- 新增策略自动出现在图例中

### CSS 适配
- 卡片布局使用 CSS Grid / Flexbox
- 3个策略：一行3列
- 4-5个策略：自动换行或滚动
- 颜色变量从 API 动态注入，无需预定义

---

## 九、复盘总结功能

### 数据持久化方案
复盘数据存储在 `review/` 目录：

```
review/
├── 2026-06-08.json     # 每日复盘数据
├── 2026-06-09.json
└── summary.json        # 累计统计
```

### 复盘文件格式
```json
{
  "date": "2026-06-08",
  "summary": {
    "total_asset": 30462.05,
    "total_return": 1.54,
    "best_strategy": "r32",
    "worst_strategy": "zhuidian"
  },
  "strategies": {
    "qixing": {
      "total_return": -3.77,
      "trades": [...],
      "notes": "创业板回调，符合预期"
    }
  },
  "notes": "今日市场整体震荡..."
}
```

### 复盘页面功能
- 历史日期选择器
- 策略当日表现对比
- 交易记录时间轴
- 手动笔记编辑区
- 累计收益曲线（跨日）

---

## 十、向后兼容说明

| 版本 | 文件 | 说明 |
|------|------|------|
| V1.0 | `real_data_server.py` | 硬编码三策略，已归档 |
| V1.0 | `data.js` | 硬编码三策略，保留兼容 |
| V2.0 | `real_data_server_v2.py` | 动态策略配置（推荐） |
| V2.0 | `data_v2.js` | 动态策略前端（推荐） |

迁移路径：
1. 复制 `config/strategies.json` 和 `signals/` 文件
2. 启动 `real_data_server_v2.py`
3. 前端改用 `data_v2.js`
4. 旧文件保留作为备份
