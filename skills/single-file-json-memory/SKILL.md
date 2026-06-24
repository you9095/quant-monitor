---
name: single-file-json-memory
label: 项目隔离单文件记忆技能
version: 1.0
description: AI量化三策略监控面板项目专属记忆入口；结构化工作日志保存在项目根目录下的 project_memory/memory.json。
category: storage
author: Hermes Agent
created: 2026-06-13
---

# 项目隔离单文件记忆技能

## 适用范围
仅适用于 `ai_quant_three_strategy_monitoring_panel`，即 `/Users/junze/quant-monitor-local`。

## 固定文件
- 记忆文件：`/Users/junze/quant-monitor-local/project_memory/memory.json`
- 导入缓存：`/Users/junze/quant-monitor-local/project_memory/log_import_cache.json`
- 原始日志目录：`/Users/junze/quant-monitor-local/logs`

## 触发词
- 保存记忆、记录日志、导入工作日志、查看记忆库状态
- 查找记忆、搜索日志、查看全部记忆、作废该记忆

## 强制规则
1. 只读写当前项目根目录下的 `project_memory/memory.json`。
2. 原始日志保留在 `logs/`，只读，不移动、不删除、不覆盖。
3. 删除只能软删除：将 `memory.json` 中条目 `status` 改为 `invalid`。
4. JSON 损坏时停止写入，保留现场，提示人工修复。
5. 不依赖网络、云端数据库或外部 API。
6. 记忆文件纳入项目 Git 管控，随项目打包迁移。

## 标准操作
- 新增日志：写入 `logs/工作日志_YYYY-MM-DD_主题.md`，再导入到 `memory.json`。
- 检索日志：读取 `memory.json`，仅返回 `status=valid` 的条目。
- 查看状态：读取 `meta` 与 `memory_list` 统计有效条目数量。
- 导出备份：复制 `project_memory/memory.json` 到备份目录。

## 当前项目策略
- 七星策略：R120，年化 32.35%、回撤 -6.58%、夏普 2.15、Calmar 4.92、40 笔交易。
- 三驾马车策略：R32，2Y 回测 +38.14%、回撤 -9.16%。
- 追电策略：版本 1.0，需继续补齐最新策略结果与监控面板同步状态。

## 验收口径
任一策略完成棘轮迭代后，必须同步到监控面板，并验证：
1. 后端 `/api/v1/dashboard/overview` 返回最新 `metrics`。
2. 前端卡片与详情弹窗展示最新轮次、数据期、指标与持仓。
3. 最新策略结果文件、后端数据源、前端展示三者一致。
