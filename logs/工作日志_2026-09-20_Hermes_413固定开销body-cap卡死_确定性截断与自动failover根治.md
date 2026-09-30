
---

## 十、方案 A 落地：保留手动切模型能力 + 一键切回默认
用户拍板方案 A——保留"手动切 GLM/智谱/OpenRouter"能力，同时堵上"硬切后停在非默认、自动 fallback 不会替你切回"的缺口。

### 新增三个文件
1. `~/.hermes/state/model_switch_baseline.json`：出厂默认基准（default=nemotron-ultra-550b:free，provider=openrouter）。
2. `~/.hermes/scripts/model_switch_rollback.sh`（chmod +x）：一键切回。读 baseline → 备份 config → 只 sed 改 model 段 2 空格缩进的 `default`/`provider` 两行（providers 块键名不是 default/provider，不会误伤）→ awk 校验 → kickstart gateway；幂等，已是默认直接退出。
3. `~/.hermes/scripts/glm_switch.sh`：在"改 4 字段"前插一行快照（复用已有 `field()`），写 `state/model_switch_last.json`（before_default/before_provider/target/ts）。原文件备份 `glm_switch.sh.bak.20260920_rollback`。
   - 564 行的 switch_model.sh 不动（被量化 cron llm_fallback_cron 依赖，其切 openrouter 免费方向安全）。

### 端到端验证
- `glm_switch.sh glm-4-flash`：config 变为 default=glm-4-flash / provider=zai，快照正确记录 before=ultra/openrouter。
- `model_switch_rollback.sh`：一键恢复 default=ultra / provider=openrouter，gateway 平滑重载（新 PID 63624），二次运行提示"已是默认"。
- ultra oneshot 15.4s 成功，无 glm/zai/deepseek/413/no reply。

### 边界规则（已写入 MEMORY v8）
- 触发词：用户说"切回默认模型/恢复默认/切回 openrouter 默认/撤销切模型/回到主模型" → 直接 `bash ~/.hermes/scripts/model_switch_rollback.sh`。
- 自动 fallback 只走 config.yaml fallback_providers + 会话内 try_activate_fallback，自动进程绝不硬改 model.default；shell 切换器仅限用户显式点名切到非 OpenRouter 官方 provider（GLM/MiniMax 自有 key）时用，切完必可 rollback。
- 已知旧瑕疵（不影响功能）：glm_switch.sh 末尾校验报"切换失败"是因为它按旧结构在 model 段找 api_mode/base_url，而新 config 这两字段在 providers.zai 块（4 空格缩进）；实际 provider=zai 已生效、运行时从 providers 块读取，属误报。

### 可选小优化（用户未要求，暂未做）
update_free_fallback_pool.py 仅在池子变化那天用 yaml.dump 整写 config 会丢注释（顺序已保序：kept 保持原序、新增追加链尾）；如需保留注释可换 ruamel.yaml，不紧急。
