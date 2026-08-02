# 三策略监控面板 · 五策略监控

> A 股 ETF 轮动专项监控面板 — 自部署、本地优先、聚焦数据准确性
> 覆盖：七星策略 / 三驾马车 R32 / 追电 ETF 动量 / 三合 R25_vol_weight / 闪电 R4_m3

---

## 一句话价值

把棘轮迭代产出的 5 套 ETF 轮动策略，**从研究到监控放在一张桌子上**——你再也不用来回切窗口确认"面板是不是最新版本"。

---

## 5 分钟跑起来

### 前置条件
- Docker Desktop（macOS / Linux / Windows）或 Docker Engine + Compose v2
- 端口 8000（可自定义）

### 一键安装（生产环境）

```bash
curl -fsSL https://raw.githubusercontent.com/you9095/quant-monitor/main/install.sh | bash
```

默认装到 `~/quant-monitor`，启动后访问：

```
http://localhost:8000
```

### 本地开发（无 Docker）

```bash
cd ~/quant-monitor-local
bash start.sh           # 端口 8000
bash start.sh 8080      # 自定义端口
```

---

## Why 三策略监控面板

| 传统工作流 | 三策略监控面板 |
|-----------|---------------|
| 棘轮迭代结果只在 reports/ 下，要去翻文件夹 | 面板首页直接看 5 策略最新版本 + 数据期 + 口径 |
| 多策略散落在不同脚本，切换窗口麻烦 | 一张桌子 5 张策略卡，30 秒自动刷新 |
| 行情 API、信号文件、metrics 文件分散 | 统一 `/api/v1` 接口，前端单端口访问 |
| 告警要靠人肉盯 | 后台 5 分钟自动健康检查，异常飞书推送 |

---

## Safety model

- **本地优先**：所有数据留在用户自己的部署，不上传任何云服务
- **后端代码安全**：SECRET_KEY 不留硬编码（如未来加鉴权层）
- **监控只读**：面板没有任何"执行/下单"按钮，仅监控不操作
- **审计日志**：所有告警写入 `logs/alerts.log`，可溯源
- **频控保护**：同类型告警 5 分钟内不重复推送，避免轰炸

---

## Technical highlights

| | 差异化点 |
|---|---------|
| **A 股 ETF 专项** | 涨跌停规则、交易时段、申赎限制、北向资金、A 股专属 ETF 折溢价 |
| **5 策略统一监控** | 七星 / 三驾马车 R32 / 追电 / 三合 / 闪电 一站式展示 |
| **动态策略配置** | 策略从 `config/strategies.json` 加载，新增策略无需改代码 |
| **棘轮迭代闭环** | 棘轮迭代完成后通过 `sync_strategy_results_to_monitor.sh` 一键同步到面板 |
| **飞书告警内置** | 后台 5 分钟健康检查 + 频控 + 审计日志 |
| **单端口 Docker** | 一个端口搞定前端 + API，零外部依赖 |

---

## Features at a glance

- **监控视图**：5 张策略卡 + 净值曲线 + 今日动作条 + 风险监控 + 策略变更日志
- **盘后复盘**：独立 `/review` 页面，汇总当日数据
- **动态策略**：策略数量由 JSON 配置决定，前端自适应渲染
- **告警系统**：信号滞后 / 回撤超阈值 / 磁盘满，5 分钟频控推送飞书
- **数据溯源**：每个策略显示数据期、引擎版本、口径
- **快捷键**：1/2/3 打开策略详情，R 刷新，Esc 关闭弹层

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Browser  (Vue SPA, 单文件 index.html)  │
└────────────────┬────────────────────────┘
                 │ /api/v1/* (相对路径)
┌────────────────▼────────────────────────┐
│  Flask Backend (single port 8000)       │
│  ├── /api/v1/strategies                 │
│  ├── /api/v1/dashboard/overview         │
│  ├── /api/v1/{sid}/positions            │
│  ├── /api/v1/{sid}/today_actions        │
│  ├── /api/v1/{sid}/status               │
│  ├── /api/v1/alerts/check (health)      │
│  ├── /api/v1/alerts/trigger (manual)    │
│  ├── /api/v1/alerts/history             │
│  └── /<path> 静态文件 (index/review/...)│
│                                          │
│  + Background scheduler (5min health)    │
└────────┬────────────────────┬───────────┘
         │                    │
┌────────▼─────────┐  ┌───────▼────────────┐
│ signals/*.json   │  │ config/strategies  │
│ (棘轮迭代产出)   │  │ .json (策略清单)   │
└──────────────────┘  └────────────────────┘
```

**运行时数据流**：
1. 棘轮迭代任务产生 `signals/{strategy_id}_{date}.json`
2. Flask 后端每 30 秒读取信号文件 + 实时行情
3. 前端 30 秒轮询 `/api/v1/dashboard/overview`
4. 后台 scheduler 每 5 分钟跑健康检查，异常推飞书

---

## 安装

### Docker（推荐）

```bash
git clone https://github.com/you9095/quant-monitor.git ~/quant-monitor
cd ~/quant-monitor
docker compose up -d --build
```

打开 http://localhost:8000

### 一键脚本

```bash
curl -fsSL https://raw.githubusercontent.com/you9095/quant-monitor/main/install.sh | bash
# 或指定目录
curl -fsSL ... | bash -s -- /opt/quant-monitor 8080
```

### 本地开发

```bash
cd ~/quant-monitor-local
bash start.sh
```

详见 `start.sh` 自动建 venv + 装依赖 + 启动服务。

---

## 棘轮迭代同步流程

每次棘轮迭代完成后，必须把最新结果同步到监控面板：

```bash
./scripts/sync_strategy_results_to_monitor.sh qixing /path/to/qixing_R120_results.json
```

会自动：
1. 生成 `signals/qixing_{date}.json`
2. 更新 `review/{date}.json`
3. 后端下次轮询（30 秒内）自动加载

详见 `references/latest-ratchet-sync.md`

---

## 项目结构

```
.
├── api/                       # Flask 后端
│   ├── real_data_server_v2.py # 主服务（动态策略 + 告警 + 静态托管）
│   └── alerts.py              # 告警模块（飞书推送 + 频控 + 审计）
├── assets/                    # 前端数据层
│   ├── data.js                # 3 策略版
│   └── data_v2.js             # 5 策略动态版
├── config/                    # 策略配置
│   ├── strategies.json        # 策略清单（名称/颜色/版本）
│   └── alerts.json            # 告警阈值
├── signals/                   # 信号文件（棘轮迭代产出）
├── review/                    # 复盘数据
├── metrics/                   # 指标历史
├── logs/                      # 审计日志 + 服务日志
│   ├── alerts.log             # 告警记录
│   ├── server.log             # Flask 服务日志
│   └── .alert_state.json      # 频控状态
├── index.html                 # 主监控面板
├── review.html                # 盘后复盘页
├── scripts/
│   └── sync_strategy_results_to_monitor.sh  # 棘轮迭代同步脚本
├── install.sh                 # Docker 一键安装
├── start.sh                   # 本地开发启动
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 常用命令

```bash
# 启动服务（Docker）
docker compose up -d

# 启动服务（本地）
bash start.sh

# 查看实时日志
docker compose logs -f           # Docker
tail -f logs/server.log          # 本地

# 触发健康检查
curl http://localhost:8000/api/v1/alerts/check

# 手动触发告警（测试）
curl -X POST -H "Content-Type: application/json" \
  -d '{"title":"测试告警","message":"验证飞书通道","alert_type":"info","force":true}' \
  http://localhost:8000/api/v1/alerts/trigger

# 查看告警历史
curl http://localhost:8000/api/v1/alerts/history | python3 -m json.tool

# 棘轮迭代同步
./scripts/sync_strategy_results_to_monitor.sh <strategy_id> <result_json>
```

---

## FAQ

### Q：面板数据多久更新一次？
A：策略数据 30 秒轮询，行情数据 5 秒轮询。棘轮迭代完成后调用同步脚本，下一次轮询即可看到。

### Q：怎么新增策略？
A：编辑 `config/strategies.json` 加一行配置即可，无需改代码。

### Q：怎么接入实盘下单？
A：当前**只有监控功能，无下单按钮**。如未来接实盘，需先实现策略 promote 闸门 + SECRET_KEY 校验 + 审计日志（详见 P1 路线图）。

### Q：飞书告警怎么关闭？
A：编辑 `config/alerts.json`，把 `cooldown_minutes` 设为 99999，或删除该文件回退到默认配置。

### Q：数据延迟了怎么办？
A：先看 `logs/server.log` 检查行情 API 是否正常，再看 `logs/alerts.log` 最近告警。

### Q：和 GitHub Pages 部署的区别？
A：Docker 单端口方案适合私有部署；GitHub Pages 适合公开只读访问但无 API（详见 `DEPLOY_GUIDE.md`）。

---

## License

仅个人自用项目，不开源。

## 路线图

详见 `references/quantdinger-v2-roadmap.md`（对标 QuantDinger 的 v2 演进路线）。

## 数据隐私策略 (2026-08-02)

本仓库严格区分公开代码与私密数据。

**GitHub Pages 公开版本**（任何人能访问 https://you9095.github.io/quant-monitor/）：
- 仅显示脱敏 mockData（portfolio.total_value: 50000，无真实盈亏数字）
- 不显示真实持仓 / 真实盈亏 / 真实交易数据
- 部署文件仅含代码结构 / 配置 / 静态资源

**用户本机私有版本**（仅用户本机 Docker 部署可见）：
- 真 portfolio_summary（总资金 / 总盈亏 / 5 策略分项）
- 真信号文件 signals/
- 真后端 Flask api/

**自动化隔离机制**：
- crontab 工作日 16:30 同步真 portfolio 到本机 assets/data.js，**不 push 到 origin**
- 真数据源 signals/ + api/ + review/*.json + results/*.json 全部 `.gitignore` 排除
- 真后端数据仅本机 Docker 容器可见，公开 Pages 永远无法访问

**撤回历史**：
- 2026-08-01 commit `07824b9` 曾误推真 portfolio 数据到公开 Pages（86146 / 36146 / 72.29%）
- 2026-08-02 commit `f6d2760`「Revert "data: 路径3 本机cron同步真portfolio_summary到assets/data.js"」撤回
- 2026-08-02 commit `83c5425` `.gitignore` 增 3 条真数据保护规则
- 撤回后公开 Pages 恢复脱敏状态（portfolio.total_value: 50000）