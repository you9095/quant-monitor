# 工作日志 · 2026-09-20 · Hermes 413「固定开销 body-cap」卡死根治：确定性截断 + 自动 failover 到宽松上游

## 一、现象（用户诉求）
- 微信公众号抓取等会话出现 `Request payload too large (413). Cannot compress further.`，随后
  `Context compression is temporarily paused ... (structural_backoff)`，连续发「继续」都被软拒绝，
  任务卡死、必须人工干预。
- 更反常：修复 9-19 聚合器误路由后，一个**全新的、只有「回一个字：通」的 oneshot 会话也直接 413 卡死**。
- 用户铁律不变：**任何报错（429/404/413/No reply）都必须全自动恢复，绝不卡住、不需要手动 continue；默认只用免费模型。**

## 二、根因（有实测数据，不是推测）
1. 9-19 修好「聚合器 slug 被误路由到同名官方 provider」后，主模型 `deepseek/deepseek-v4-flash-0731:free`
   才真正经 OpenRouter 打到其上游 **OpenInference**。
2. `hermes prompt-size --json` 实测 Hermes 每个会话的**固定请求开销**：
   - system prompt **223,668 B（158,885 字符）**
   - skills 索引 54,050 B
   - tools schema 39,553 B（24 个工具）
   - memory 17,743 B + user_profile 1,531 B
   - 合计固定前缀 **≈ 335KB（还没算 AGENTS.md/SOUL.md 各被截到 20KB 与任何对话历史）**。
3. 直接对上游打不同 body 大小（经 OpenRouter，同 key）：
   | 上游 / 模型 | system 100KB+历史40KB(280KB) | 526KB | 686KB |
   |---|---|---|---|
   | OpenInference / deepseek-v4-flash:free | **HTTP 413 Request too large** | 413 | 413 |
   | Nvidia / nemotron-3.5-lightning:free | 200 OK | 200 OK | 200 OK |
   → **OpenInference 免费 relay 的 body 上限 < 280KB，根本装不下 Hermes 的 335KB 固定前缀**；
   而 fallback 链上的 Nvidia 免费上游 686KB 都能收。
4. 因此**任何**真实 agent 会话发给主模型都会 413，与对话长短无关。此前「能用」是因为主模型一直被
   误路由 400、实际靠 fallback 的 nemotron 在扛——9-19 路由修好后这个上游容量硬伤才暴露。
5. 为什么原有压缩/恢复机制拦不住：
   - 413 是**字节数**错误，且超限部分在**固定前缀（system/skills/tools）**，不在 `messages` 历史；
   - LLM 压缩对短会话「无旧历史可折叠」→ `failure_class=no_progress`、`aux_model=""`、`commit_status=aborted`；
   - 唯一的非 LLM 兜底 `_try_strip_image_parts_from_tool_messages` 只剥 tool 消息里的图片，不碰巨型
     字符串/HTML/JSON，更不可能缩小固定前缀；
   - 失败即 `fail_turn` 并 arm `_STRUCTURAL_NO_OP_BACKOFF_SECONDS=300`，冷却期内所有 turn（含「继续」）
     被 `compression_blocked_transiently` 软拒绝 → 表现为卡死。

## 三、修复（三层，全部在活代码根 /Users/junze/Apps/hermes-agent-v2026.6.5）
### 1) 确定性、不依赖 LLM 的输入截断（兜底历史/媒体型 413）
- `agent/message_sanitization.py` 新增纯函数
  `_truncate_text_to_byte_limit()` 与 `force_truncate_oversized_messages(messages, *, target_bytes)`：
  先剥**所有**消息图片 → 保护最后一条 user 指令 → 绝不改 tool_call 的 arguments、绝不删 tool 消息
  （避免孤儿 tool_call_id 触发 400）→ 按四轮收紧的单块上限（tool 20000/8000/3000/1200B，
  other 40000/16000/6000/2500B）循环砍 str 文本与 list 内 text part，中间插带字节计数的截断 marker。
### 2) 413 恢复路径接入截断 + 解除 structural backoff
- `agent/turn_overflow.py::_recover_payload_too_large`：图片剥离无效后调用上面的确定性截断；
  成功则清掉 `_structural_no_op_backoff_until` / `_summary_failure_cooldown_until`、同步历史、
  persist、置 `restart_with_compressed_messages=True` 自动重启调用。
- **关键**：不再在 `st.compress()` 返回 deferred（structural backoff / 压缩锁）时提前 return——
  那正是「每个 continue 都被拒」的死锁点；确定性截断/failover 不依赖 LLM、不受该 backoff 影响，
  改为继续下落（压缩进展仅在 `deferred is None` 时采信）。
### 3) 固定开销型 413 → 自动 failover 到 body 宽松的上游（本次新增，根治新会话也卡死）
- `agent/turn_overflow.py` 新增 `_failover_body_cap_provider()`：当压缩/剥图/截断都无法让请求变小时
  （= 超限来自固定前缀），把当前 `(provider, model)` 经
  `_mark_permanent_model_failure(..., reason="payload_too_large")` 标记为**本会话 body-cap 不兼容**
  （fallback walk 跳过、restore_primary_runtime 不切回，避免横跳），随后 `_try_activate_fallback`
  + `_arm_fallback_restart` 切到链上下一个上游并 break 重启；只有整条链都不可用才终止 turn。
- `agent/fallback_cooldown.py::_mark_permanent_model_failure` 增加 reason 感知：
  `payload_too_large` 用「request body 超上游上限」文案，不再误报健康模型「model retired / 404」。
- 顺序保证：历史/媒体型先就地截断（同一 provider 重试，不浪费切换）；只有 messages 已砍到最小仍 413
  才判定为固定前缀超限、切换上游。

## 四、测试与验证
- 新增 `tests/agent/test_413_body_cap_failover.py`（5 用例，全过）：小 payload 413 自动切模型并标记、
  structural backoff 下不再 parked、链耗尽才终止、巨型 tool 结果先就地截断不切换、body-cap 标记文案。
- 既有 `tests/agent/test_413_deterministic_truncation.py` 10 用例全过。
- 回归：413/overflow/fallback 相关 12 文件 **114 passed**；永久黑名单 + restore-primary 等 **95+6 passed**。
  唯一 1 失败 `test_413_compression.py::...[provider_error-3]` 经 **git HEAD 基线 A/B 对比同样失败**
  （环境缺可选模块 `nemo_relay`），与本次改动无关。
- **端到端（决定性）**：修复前 `venv/bin/hermes -z "回一个字：通"` 两次稳定返回
  `Request payload too large (413). Cannot compress further.`；修复并重启 gateway 后同样命令成功返回「通」。
  已确认两个 shell hook（`auto_model_router.py` 只按触发词切 deepseek/minimax；
  `openrouter_or_429_immediate_switch.py` 状态码集合 {429,402,403,404,500,502,503,529,530}）
  **都不含 413**，故成功只能来自新的代码级 body-cap failover。
- cron 无人值守会话日志亦见 `Fallback activated ... → nvidia/nemotron-3.5-lightning:free` 后正常 Turn ended。

## 五、备份 / 回滚
- `agent/message_sanitization.py.bak.20260920_413trunc`
- `agent/turn_overflow.py.bak.20260920_413trunc`（截断版）、`agent/turn_overflow.py.bak.20260920_413failover`（failover 前）
- fallback_cooldown.py 可 `git checkout -- agent/fallback_cooldown.py`（git 已跟踪）
- 回滚：`cp <bak> agent/turn_overflow.py` 等；测试双份存于豆包工作目录与 repo tests/。

## 六、遗留与后续建议（不影响「不卡死」，属优化）
1. **system prompt 223KB 异常臃肿**是 OpenInference 装不下的深层原因；长期应精简 system/skills 索引，
   或把主模型直接换成 body 上限宽松的免费上游（如 nemotron 系），可免去每次新会话先撞一次 413 再切换。
2. oneshot 为新进程、会话级标记不跨进程，故每个新会话首次仍会有一次快速 413→切换（约 1–2s，全自动、不卡）。
3. **机制仍有重叠**：代码级 fallback 链（config.yaml，会话内可 restore）与 shell hook
   `openrouter_or_429_immediate_switch.py`（外部脚本改全局 model.default，处理 429/5xx）、
   `auto_model_router.py`（触发词改 model.default）是两套并行机制。本次已让 413 统一走代码级链；
   是否下线旧 hook 需按「先确认无用再删、mv 归档不 rm」另行评估，勿在本次擅自删除。
4. 既有遗留：`nemo_relay` 可选模块缺失致 1 个基线测试失败；update_free_fallback_pool 热度排序因 pricing 全 0 无区分度（功能正常）。

---

## 七、收尾（当日 13:30）：主模型更换 + fallback 按容量实测重排
413 failover 修好后，为免去每个新会话先撞一次主模型错误再切换，做容量实测并更换主模型。

### 发现：旧主模型免费端点已下线
- `deepseek/deepseek-v4-flash-0731:free` 经 OpenRouter 连续 2 次返回 **HTTP 404 "This model is unavailable for free. The paid version is available"**——免费端点下线、只剩付费。这是比 413 更彻底的不可用，按"默认只用免费"铁律必须换掉。

### 容量实测（~400–800KB body，OpenRouter 同 key）
| 模型 | 裸测 800KB | 真实 oneshot（完整 335KB 前缀）| 结论 |
|---|---|---|---|
| nvidia/nemotron-3-ultra-550b-a55b:free | 200 | **0-fallback，13–14s，推理正确** | **选为主模型**（550B 旗舰、容量足）|
| nex-agi/nex-n2.5-mini:free | 200 | 0-fallback，8–11s，推理正确 | fallback 第 1（最快备份）|
| inclusionai/ling-3.0-flash-sante:free | 200 | 0-fallback，13s | 前置 |
| nemotron-super / nano-omni / nex-pro / ling-vl | 200 | — | 前置/中段 |
| nemotron-3.5-lightning:free | 200 | 0-fallback 但 76s | 容量 OK、慢，保留兜底 |
| qwen3.8-27b:free | 429 / 30s | — | 后置 |
| poolside/laguna-xs-2.1:free | 偶空回复 | — | 后置 |
| cohere/north-mini-code:free | 502 | — | 后置 |
| liquid/lfm-2.5-2.6b:free | 400 maximum context | — | 窗口小，仅小 payload 兜底 |
| deepseek-v4-flash:free | **404 免费下线** | — | 移除主模型位 |

### 改动（备份 config.yaml.primarybak.20260920_133250）
1. `model.default` → `nvidia/nemotron-3-ultra-550b-a55b:free`（provider 仍 openrouter）。
2. fallback 重排为 12 条：移除与主模型重复的 ultra（去重）；nex-mini / ling-sante / super / nano-omni 提前，慢或偶发错误的 qwen/poolside/cohere/liquid 后置，zai/glm-4-flash 异源兜底最后。全部 openrouter 条目均 `:free`。
3. 新增 `~/.hermes/scripts/check_primary_body_cap.py`（豆包工作目录双份）：解析 config + 免费审计 + 用 ~340KB 固定前缀实测主模型，413→BODY_TOO_SMALL、404→FREE_UNAVAILABLE、429 单列不否决，`--all` 探全链。换主模型 / 每日更新池后应跑。

### 验证
- YAML 解析：主模型 ultra、链 12 条非空、无免费违规、ultra 已去重。
- 默认 `hermes -z`（不带 -m，走完整 hooks 启动路径）连续 2 次 0-fallback 直接成功，输出无 deepseek/413/404/No reply。
- 健康脚本 PASS（主模型 200、承载 700KB）。
- gateway `launchctl kickstart` 重启后 state=running、新 PID、必需 key 全 OK、无 traceback。
- 注：裸 API 用 250KB 重复单字填充曾测到 97s，系重复 token prefill 假象；真实 system 文本 oneshot 为 13–14s，以真实负载为准。

### 遗留（另案）
- hooks `pre_llm_call/auto_model_router.py` 命中特定触发词仍会调 `deepseek_minimax_switch.sh` 把 model.default 切到 deepseek/minimax，而免费 deepseek 已下线——这是「代码级 fallback 链 vs shell hook」两套并行机制的最后重叠点。按"先证实无用、mv 归档不 rm"原则另案处理，本次不擅删。
- 桌面 GUI（Hermes.app，长连接）若缓存旧模型，重启一次 App 即可；gateway / cron / CLI 已即时生效。

---

## 八、下午续：下线旧模型路由 shell hook（deepseek 切换器归档，hooks 收敛为 2 个）
换主模型后，清除"代码级 fallback 链 vs shell hook"两套并行机制的最后重叠点（用户指示：下线的就删除，按惯例 mv 归档可回滚）。

### 排查结论（config 实际启用的 6 处 hook 接线，逐一读码 + 交叉引用实证）
| hook（事件） | 状态 | 依据 |
|---|---|---|
| auto_model_router.py（pre_llm_call） | **下线·有害** | 2026-08 旧 MiniMax-M3↔deepseek 二选一路由；命中 26 个高频触发词（深度复盘/架构设计/深度分析/完整闭环/反查根因/顶层设计…）即 sed 把 provider/base_url 整体改成官方**付费** api.deepseek.com（模型名还可能不被认）或 minimax-cn，openrouter 免费链随之全失效；日志停在 8-03 |
| pre_session_init.py（on_session_start） | **下线·已死** | 依赖 9-19 已归档的 openrouter_fallback.sh；state/openrouter_fallback.state 不存在，永久 no-op；目标还是切回 MiniMax-M3 |
| openrouter_or_429_immediate_switch.py（post_api_request + api_request_error，2 处） | **下线·已死** | spawn 的核心 or-429-immediate-switch.py 活文件已缺失（仅 .bak）；只写活代码 0 读取的 chain.<profile>.json；功能已被代码级 try_activate_fallback 完全取代；日志停 9-07 |
| glm_thinking_router.py（未启用） | **下线·死文件** | config 0 引用 |
| quant_monitor_trigger_hook.py（pre_llm_call） | **保留** | 量化项目命中触发词注入 skill 加载提示，不切模型 |
| openrouter_concurrency_gate.py（pre_tool_call/delegate_task） | **保留** | 限制 openrouter 免费模型并发 ≤1，与免费链配套，不切模型 |

交叉引用（config 非 hooks 段 / 内部 cron jobs.json / 系统 crontab / 保留 hook / 活 cron wrapper / llm-defense）证实旧切换家族 deepseek_minimax_switch、recognize_model_switch、glm_switch、deepseek_switch、auto_switch、send_minimax_skill **全部 0 活引用**。

### 保留的活机制（勿删）
- switch_model.sh + llm_fallback_cron.sh：系统 crontab 的量化任务（goldcombo_2y/5y、ab_comparison）失败且命中 LLM 错误时，切到 openrouter（Ling 系 :free，实测可用）等 45s 重跑一次。
- llm-defense 守护体系（hermes-gateway-wrapper / hermes-supervisor / gateway-401-watchdog / 各 health-check）：不碰模型切换。

### 执行（备份 config.yaml.hookclean.bak.20260920_142015，mv 归档不 rm）
- config hooks 删除 4 处接线，仅留 quant_monitor（pre_llm_call）+ concurrency_gate（pre_tool_call）。
- hooks/_archive_20260920/：auto_model_router.py、pre_session_init.py、openrouter_or_429_immediate_switch.py、glm_thinking_router.py、concurrency_gate 的 .bak。
- scripts/_archive_20260920/legacy_deepseek_switchers/：deepseek_minimax_switch.sh、deepseek_switch.sh、recognize_model_switch.py（+3 个备份）、or-429 核心 .bak。

### 验证
- YAML 合法；hooks 段仅剩 2 个活 hook；config 无任何已归档文件残留引用。
- 密集触发词 oneshot（"深度复盘/架构设计/完整闭环/反查根因/顶层设计"）：exit 0、正常产出、无 deepseek/无切换提示/无 413/404；**跑完 config 主模型仍 nemotron-ultra、provider 仍 openrouter**（证明不再被 hook 切走）。
- gateway kickstart 后 state=running（新 PID 25475），无 hook 缺失/归档文件报错（Lark 1000 为飞书 websocket 重启重连正常关闭码）。
- 极简 oneshot 7.6s 成功、零异常。

### 回滚
`cp config.yaml.hookclean.bak.20260920_142015 config.yaml && mv hooks/_archive_20260920/*.py hooks/ ...`（归档目录原样保留）。

### 仍遗留（无自动入口、不会自跑，本次未动，可后续归档）
- scripts 中 glm_switch.sh、auto_switch.sh、send_minimax_skill.py、post-model-switch-recovery.sh、takeover/tui-stuck watchdog 等 minimax/glm/看门狗旧家族。
- switch_model.sh 默认从已废弃的 state chain.json 选 Ling，可后续改为读 config.yaml fallback_providers 首选。

---

## 九、下午续二：第二轮死脚本清理（白名单核查）——自动模型路由确认已统一
用户要求继续清理剩余旧脚本。因涉及看门狗，改用**白名单法**（先列活调度源引用的脚本，再做差集），而非按文件名想当然。

### 9.1 重大纠正：看门狗几乎全是活的（v6 文档"可后续归档看门狗"说法作废）
- 系统 crontab 活跃：tui-stuck-watchdog（每1分）、orphan-process-cleanup（每2分）、takeover-watchdog（每10分）、tmpfs-code-sign-cleanup（每月）、bin/hermes-healthcheck + bin/hermes-model-watchdog（每30分）、update_free_fallback_pool.py（每天6:00）、llm_fallback_cron（量化 goldcombo/ab_comparison）。
- launchd（ai.hermes.*）活跃：gateway→llm-defense/hermes-gateway-wrapper.sh、gateway-401-watchdog、hermes-supervisor-follow、disk-watchdog、platform-health、proxy-health、llm-health-report、llm-key-probe、ccam_monitor、museum_monitor_priority、p9/walk_forward_runner、p9/ab_quarterly_eval。
- 结论：watchdog/health/monitor 类一律保留。

### 9.2 自动模型路由现状——已统一到 config.yaml fallback_providers 单一事实来源
| 入口 | 触发 | 动作 | 判定 |
|---|---|---|---|
| 代码级 try_activate_fallback | 每次请求遇 413/404/429/空回复 | 读 config fallback 链自动切 | 主，保留 |
| update_free_fallback_pool.py | launchd/cron 每天 6:00 | 直接读写 config.yaml fallback_providers（双因子判免费、剔除转收费、写前 pool.bak、平滑重载 gateway） | 保留，"每日更新"真实生效 |
| bin/hermes-model-watchdog | 每30分 | 只读 curl 探测 + 硬编码死模型清单，仅告警/exit 码，**不改配置** | 安全，保留（只查 profiles/ 子目录） |
| switch_model.sh + llm_fallback_cron | 量化 cron 失败 | 切 openrouter Ling 系免费重跑 | 子系统专用、方向安全，保留 |

### 9.3 本轮归档（仅 1 个，0 争议）
- send_minimax_skill.py → scripts/_archive_20260920/legacy_oneoff_notifiers/：一次性飞书群硬编码"minimax-skills 安装完成"通知，全目录 0 引用。

### 9.4 经核查保留 / 不在本轮范围
- glm_switch.sh、auto_switch.sh：被约十几个仍 available 的"手动切模型 skill"引用（model-routing/glm-zhipu-ai、model-switch-hard-cut-lifecycle、model-switch-request-recognition、switch-model-health-check-mandate、hermes-platform-ops/{deepseek-model-switch,model-routing-troubleshooting,openrouter-model-pool,openrouter-429-immediate-switch}、hermes-model-routing-policies、devops/llm-fallback-cron、agent-workflow 章节）。它们只在用户显式说"切 GLM/切 OpenRouter"时触发（§21 手动覆盖通道），自动 hook 已在第八节拆除，不会自动跑。
- rate_limit_guard.py：未接线的独立 429 参考模块；活代码实际用内置 turn_api_call.py 的 nous_rate_limit_guard，不 import 此文件；429 主题敏感，暂留。
- scripts 顶层 69 个"0 自动引用"脚本：多为量化/飞书/升级迁移/内存分层/一次性业务脚本或手动体检工具（如自建 check_primary_body_cap.py），与模型路由无关，保守不动，避免误删业务资产。

### 9.5 待用户拍板 + 已知小风险
- 待决策：手动切模型 skill 簇 + sed 切换器（glm_switch/auto_switch）整体保留（保留一句话切 GLM 官方/子模型能力，代价是自动+手动两套需边界规则）还是整簇归档（最干净，失去手动指定 GLM 子模型/minimax 官方 key；mv 可逆）。
- 小风险（可选优化）：update_free_fallback_pool.py 用 yaml.dump 重写整个 config，池子变化时会丢注释、可能按探测顺序重排 fallback（不影响兜底成功，但覆盖手动容量/延迟排序）；可改为保序增删。
