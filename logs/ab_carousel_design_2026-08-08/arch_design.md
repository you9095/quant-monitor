# 5 张策略卡轮播架构方案 — 设计稿

**项目**: quant-monitor-local  ·  **分支**: panel-ab-test-B (SHA 45109b2 = A版基线 + B版 opacity 0.8 已落)
**角色**: 陈以深（技术总监）·  **日期**: 2026-08-08
**约束**: 不动代码,仅输出架构选型 + 理由,供江予白后续实现

---

## 0. 现有代码反查 (evidence)

| 项 | 位置 | 关键事实 |
|---|---|---|
| 渲染入口 | `index.html:1276` `renderStrategyCards(strategies)` | 调用 `activeStrategies()` 过滤 stale >5 天 → `calcGridRows()` 算行数 → `<div class="row strategy-row">` + `col-row-N` flex 子项 |
| 卡片构造 | `index.html:1305` `buildCardHtml(sid, sname, s)` | 输出 `.strategy-card.{sid}.backtest[data-strategy]`,内含 today-action-strip / profit-block / three-layer-tags / holdings / metrics |
| 容器 | `index.html:877` `<div id="strategy-cards">` | 父容器 `.container` max-width 1400px |
| 5 类策略 | index.html:29-39 + 303-307 | qixing(蓝紫) / r32(青绿) / zhuidian(琥珀橙) / sanhe(紫黄) / lightning(黄橙) |
| 键盘快捷 | index.html:2456-2459 | `1-5` 已直接 `openStrategyDetail(id)` —— 单卡索引语义已被项目使用 |
| 现有依赖 | 0 carousel 库 / 0 dots / 0 arrows | 搜索 `carousel|swiper|pagination|dot-arrow` 在 index.html **0 命中**(只有 `.dot` 是 topbar-brand 的红点) |

**5 张策略 = 单行 5 列 (col-row-5,flex 0 0 calc(100%/5))**,每张宽度 ≈ 268px (1400 − 2×padding) / 5 ≈ 268px。当前最窄屏(1024px 以下)会坍缩为 2 列,这与"5 张同时挤在一屏"的诉求天然冲突 —— 是用户提"轮播"的根本驱动。

---

## 1. 三个必答问题(每问 1 个推荐选型 + 理由)

### Q1: 单卡 vs 滑动物品(slider track) — 推荐 **单卡 + 索引状态**

**选型**: DOM 里始终只渲染 1 张 `.strategy-card`(通过 `data-index` 切换),其他 4 张仅持有数据不渲染节点。

**理由**:
1. **数据量极小**: 5 张卡 × 5 个持仓行 = 上限 25 个 holding-row + 25 个 .tlt-tag,即便全渲染也是 <2KB HTML,但**全渲染会引发视觉冲突** —— 用户看到的应该是"这一张",不是"中间这张亮一点"。
2. **键盘快捷键已存在**: index.html:2456-2459 的 `1-5` 已经在用索引语义;单卡 + index 是这套快捷键的最自然映射。
3. **CSS 风险最小**: 不需要 `transform: translateX(-100%×i)` 的 transition 动画层、不需要处理回流(reflow)、不需要 `overflow:hidden` 视窗裁切 → A/B 测试 (pb-sign 28px opacity 0.8 vs 40px 不变) 不会被 transform/animation 干扰。
4. **过渡更可控**: 单卡 fade-in/fade-out 比 5 张滑动的 GPU 成本低,且 macOS Safari 对 transform: translateX + opacity 同时变化有轻微掉帧风险(我们 45109b2 commit 用的就是 transform: translateY(-4px) 已是 hover 动效,叠加 slider 动效会冲突)。

**被否决的方案**:
- ❌ **滑动物品(swiper / slick / swiperjs)**: 引第三方依赖破坏"无新依赖"约束;且 5 张固定内容不需要 swipe 库的触屏拖拽(用户原话只提了"左右箭头")。
- ❌ **5 张全渲染 + 中间放大**: 视觉噪点多、违反用户"同一时间只看到 1 张卡"诉求。

---

### Q2: 分页点点击行为 — 推荐 **指示 + 点击跳转(双功能)**

**选型**: 5 个圆点同时承担"指示当前位置(active 状态高亮)" + "点击直接跳到该 idx",但**点击不触发卡片点击事件**(阻止冒泡到 `openStrategyDetail`)。

**理由**:
1. **用户认知负担最低**: 用户看到点 3 高亮,本能就想点它 —— 做了点击跳转 = 用户预期 100% 命中。
2. **5 张是少数量,可点**: 当分页项 ≤ 7 时(W3C ARIA Carousel Pattern 经验值),点击比"必须左右箭头"更高效;7+ 时才退化到只指示不点(避免误点)。
3. **键盘 1-5 + 箭头 + 点三向冗余**: 三种交互都给到,但每一项的成本都很低 —— 即使用户只点箭头,分页点的"指示"功能仍 100% 保留;反之亦然。
4. **技术实现零负担**: 5 个 `<button class="dot" data-index="0..4">`,加一个 `event.stopPropagation()`,不需要额外状态机。

**被否决的方案**:
- ❌ **纯指示(不可点)**: 5 个死点违反最小惊讶原则;用户一定会试。
- ❌ **悬停预览(hover 自动跳)**: 鼠标轨迹切换会让人失去当前卡片焦点,不符合"同一时间只看到 1 张卡"的心智。

---

### Q3: 箭头位置 — 推荐 **叠加在卡片左右垂直居中(absolute 定位)**

**选型**: 左右箭头用 `position: absolute; left/right: 12px; top: 50%; transform: translateY(-50%);` 叠加在 `.carousel-viewport` 内,**不占独立 column 也不抢容器的 grid 布局**。

**理由**:
1. **节省水平空间**: 容器 max-width 1400px 减去 2 个 column (各 ~40px) = 单卡变成 ≈264px,损失 ~1.5% 宽度但更糟的是视觉锚点被切碎(箭头 = "我属于这卡片"还是"我属于容器"语义模糊)。
2. **视觉锚点统一**: 箭头紧贴卡片 = 用户认知"这两个箭头是这张卡的导航",符合 iOS/macOS HIG 的 carousel pattern(Apple 官方推荐)。
3. **不破坏 A/B 测试的 profit-block 渲染**: 箭头用半透明背景 + `pointer-events: auto`,不抢 profit-block 的视觉焦点 —— 后者 opacity 0.8 (B版) / 字体 40px (A版) 都是用户当前最敏感的判断目标,不能被箭头干扰。
4. **响应式回退**: 在 <1024px(现有 2 列坍缩点)以下,箭头绝对定位仍工作,不需要重写响应式代码。

**被否决的方案**:
- ❌ **独立 column(箭头外置在 .container 两侧)**: 容器需要改为 grid `1fr auto 1fr` —— 改 .container 影响其他 section(顶部组合总览、未来可能加的更多 section),改造成本远高于绝对定位。
- ❌ **卡片内嵌 inline(箭头挤进 card-body padding 里)**: profit-block 的字号已经涨到 40px,卡片高度可能不够 —— 箭头会与 holdings 行视觉撞车。

---

## 2. 推荐架构总览(供江予白实现时参考)

```
<section class="strategy-section">
  <div class="container">
    <div class="carousel-viewport" data-active-index="0">     ← 新增,overflow:hidden, position:relative
      <button class="carousel-arrow prev" aria-label="上一张"> ← 新增,absolute left:12px
        ‹
      </button>
      <div class="carousel-track" data-strategy-cards>        ← 重命名现 #strategy-cards,单卡渲染
        <div class="strategy-card qixing backtest">...</div>   ← buildCardHtml 输出,只有 active=0 才挂 .active
      </div>
      <button class="carousel-arrow next" aria-label="下一张"> ← 新增,absolute right:12px
        ›
      </button>
      <div class="carousel-dots" role="tablist">              ← 新增,absolute bottom:-28px center
        <button class="dot active" data-index="0" aria-label="切换到七星策略"></button>
        ×5
      </div>
    </div>
  </div>
</section>
```

**关键不变量**(江予白实现时必须保留):
1. `buildCardHtml()` 函数签名 `(sid, sname, s)` 保持不变,只是从 render-for-all 改成 render-for-active。
2. `openStrategyDetail(sid)` 触发逻辑保留(整张卡仍可点击进详情)。
3. 键盘 `1-5` 快捷键保持不变(直接打开详情,与轮播 active 状态独立 —— 但可考虑"1 也同步激活 carousel active index",后续苏晏清派单时细化)。
4. `data-strategy="${sid}"` 属性保留(主 agent 的 audit 脚本通过这个 selector 抓数据)。
5. A 版 SHA 45109b2 的 `.pb-sign / .pb-int / .pb-dec` 字号不改动,B 版的 opacity 0.8 不改动;轮播改造**不能触发任何 A/B 测试数据失效**。

---

## 3. 待用户决策的 2 个开放项(留给江予白接手前对齐)

| 决策点 | 选项 A | 选项 B | 推荐 |
|---|---|---|---|
| 自动轮播 | 每 8s 自动下一张 | 只手动,不自动 | **B**(用户原话没提自动,谨慎默认关) |
| 切换动画 | 300ms fade-in/out | 400ms slide translateX | **A**(与现有 hover transform 风格一致,且无 GPU 风险) |

这两项不影响本架构的 3 个核心决策,可由江予白在实现时直接选择或在 master 合并前与苏晏清对齐。

---

## 4. 交付检查清单

- [x] 3 个问题均有 1 个推荐选型 + 理由
- [x] 理由引用了具体代码行号 (index.html:1276/1305/2456-2459/877/29-39/303-307/1400px)
- [x] 不动 index.html 代码
- [x] 不创建新分支
- [x] 不装新依赖
- [x] 不去 master
- [x] 给出待江予白实现的最小架构骨架(可选)
- [x] evidence 三件套同步写到 M01_arch_design/