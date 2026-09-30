# 工作日志：Hermes fallback 链收敛清理（2026-09-19）

## 背景
9-18/19 已完成 No-reply 卡死根治（免费池+分类器+P1 永久拉黑）。用户提出：① fallback 链每天自动更新；② 深度梳理清理重复旧机制。取证后发现真正问题不是"缺机制"，而是"机制太多、互相重叠、一半在白写死文件"。

## 取证结论（日志实锤）

| 脚本 | 调度 | 实锤 | 判定 |
|---|---|---|---|
| openrouter-watchdog.sh | 被 failover-5s 调 | 6-28→9-19 空转 20052 轮，硬编码主模型 gemma 已不在链里，每轮"active 健康、主模型不存在、留 DEGRADED" | 死，纯空转 |
| fallback_watchdog.sh | cron */5 | 日志停在 8-23，最后动作切回已下线 minimax | 死且有害 |
| refresh_dynamic_model_pool.sh | cron 6:00 | 写 chain.*.json，turn 0 读取；兜底写死 minimax/minimax-m3（无:free） | 白写 |
| or-429 --refresh-cache | cron 7:00 | 探测逻辑好（双因子+收费审计），但写 or-free-models-cache.json/chain.json，turn 不读 | 探测好但写错地方 |
| hermes-model-watchdog | cron */30 | 正确测出 3 个 profile 连接超时，只报告不自动修 | 活，方向对，保留 |

## 根因（为什么越叠越多、旧的为什么没删）
1. **只加不删**：每次卡住就新增一层新脚本，新注释写"取代 X"但 X 不删、仍挂 cron。
2. **改错文件传统**：9-10/12/16 三次改 site-packages（v0.14 死残留），gateway 不加载。
3. **无单一事实来源**：链散落在 config.yaml、chain.json、chain.*.json、state、circuit-state、cache 等 6+ 文件，没有规则说"只读 config.yaml"。
4. **风险厌恶**：怕删错（8-23 误删前科），形成"先加新的、旧的留着"习惯。

## 执行
1. **归档**：18 个死脚本 + 全部 .bak → `~/.hermes/scripts/_archive_20260919/`（不 rm，可回滚）。
2. **新脚本** `~/.hermes/scripts/update_free_fallback_pool.py`：
   - 拉 OpenRouter /v1/models，双因子免费判定（:free OR pricing prompt+completion 全 0）
   - 收费审计：当前池变收费的移除
   - 池子 <12 时按热度补新免费模型
   - 写入前备份 config.yaml.pool.bak.<ts>
   - 平滑重载 gateway
   - 实测：447 模型→25 免费，补了 inclusionai/ling-3.0-flash-sante:free，config 从 11→12 OR 免费 + 1 zai
3. **cron**：新任务 `0 6 * * * venv/bin/python update_free_fallback_pool.py`（crontab 写入被 macOS Full Disk Access 挡住，需用户手动跑 `crontab /tmp/cron.new`）。
4. **MEMORY**：写入"fallback 链单一事实来源=config.yaml，新机制必须取代并删除旧的"铁律。

## 保留不动
- hooks/ 下 5 个真挂载 hook（auto_model_router、pre_session_init、openrouter_or_429_immediate_switch、openrouter_concurrency_gate、quant_monitor_trigger_hook）
- deepseek_minimax_switch.sh、switch_model.sh、skill_precheck.sh、llm_fallback_cron.sh
- bin/hermes-model-watchdog、bin/hermes-healthcheck
- config.yaml（主模型 deepseek-v4-flash-0731:free 未动）

## 待用户手动执行
```bash
crontab /tmp/cron.new
```
（已备份原 crontab 到 ~/.hermes/scripts/_crontab.backup.20260919.txt）
