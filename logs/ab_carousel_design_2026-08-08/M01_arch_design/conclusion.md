# M01_arch_design — 3 问结论速查

**任务**: 为 5 张策略卡设计轮播架构方案
**文档**: `~/quant-monitor-local/logs/ab_carousel_design_2026-08-08/arch_design.md`
**evidence**: 本目录 `command.sh` + `raw_output.txt`

---

## 3 个必答问题结论

### Q1: 单卡 vs 滑动物品 — **单卡 + 索引状态**
- DOM 只渲染 active=1 张卡,其余 4 张数据持有但不渲染节点
- **理由**: 不引第三方库 / 不破坏 A/B 测试 (pb-sign opacity 0.8 不受影响) / 与现有键盘 1-5 快捷键语义对齐
- **否决**: swiper 库(违反"无新依赖") / 5 张全渲染(违反用户原话)

### Q2: 分页点点击行为 — **指示 + 点击跳转(双功能)**
- 5 个圆点同时承担 active 高亮 + 点击跳转到该 idx
- `event.stopPropagation()` 阻断冒泡到 `openStrategyDetail`
- **理由**: 5 项 ≤ 7(W3C ARIA 阈值)→ 可点比纯指示用户预期更命中
- **否决**: 纯指示(违反最小惊讶) / hover 预览(违反"一次只看 1 张"心智)

### Q3: 箭头位置 — **absolute 叠加在卡片左右垂直居中**
- `position: absolute; left/right: 12px; top: 50%; transform: translateY(-50%)`
- **理由**: 不抢 .container 网格(避免影响其他 section) / 视觉锚点统一(箭头=这张卡的导航) / 响应式无需重写
- **否决**: 独立 column(改 .container 牵连其他 section) / 卡片内嵌 inline(撞 profit-block 40px 字号)

---

## 关键不变量(给江予白)

1. `buildCardHtml(sid, sname, s)` 签名不变,只改 renderStrategyCards 调度
2. `openStrategyDetail(sid)` 整卡点击保留
3. 键盘 `1-5` 保留(可考虑同步激活 carousel active index,后续细化)
4. `data-strategy="${sid}"` selector 保留(audit 脚本依赖)
5. A 版 SHA 45109b2 的 pb-sign/pb-int/pb-dec 字号 + B 版 opacity 0.8 — 轮播改造**绝不触发任何 A/B 数据失效**

---

## 待对齐开放项(非阻塞)

| 决策点 | 推荐 | 备注 |
|---|---|---|
| 自动轮播 | 关 (manual only) | 用户原话没提自动 |
| 切换动画 | 300ms fade | 与现有 hover translateY 风格一致 |

---

## 停止条件 ✅

- 3 个问题均有选型 + 理由 ✅
- 不动 index.html 代码 ✅ (本会话未做任何 git 改动)
- 不创建新分支 ✅
- 不装新依赖 ✅
- 不去 master ✅
- evidence 三件套落地 ✅ (command.sh + raw_output.txt 18KB + 本文件)