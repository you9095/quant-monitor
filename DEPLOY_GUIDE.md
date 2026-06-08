# GitHub Pages 部署指南

## 安全审计状态
✅ 已通过 — 详见 SECURITY_AUDIT.md

## 部署文件清单
以下文件已提交到 Git 仓库，可安全部署：

```
index.html          ✅ 主监控面板（含复盘日期选择器）
review.html         ✅ 盘后复盘完整页面
assets/
  data.js           ✅ 数据层（仅含 localhost 开发地址）
  data_v2.js        ✅ 数据层 V2（动态策略）
config/
  strategies.json   ✅ 策略配置（名称+颜色，无敏感信息）
review/
  2026-06-08.json   ✅ 复盘数据（已脱敏）
```

## 部署步骤

### 1. 创建 GitHub 仓库
访问 https://github.com/new
- Repository name: `quant-monitor`
- Visibility: Public（或 Private + Pro 账号）
- 不勾选 "Add a README"

### 2. 推送代码
```bash
cd ~/三策略监控面板_项目档案/06_江予白_技术层
git remote set-url origin https://github.com/你的用户名/quant-monitor.git
git push -u origin master
```

### 3. 启用 GitHub Pages
1. 进入仓库 Settings → Pages
2. Source: Deploy from a branch
3. Branch: master / (root)
4. 点击 Save

### 4. 访问地址
部署完成后约 1-2 分钟生效：
```
https://你的用户名.github.io/quant-monitor/
```

## 安全说明

### 不会泄露的内容
- ❌ 密码/密钥/Token（前端代码中不存在）
- ❌ 个人隐私信息（已移除路径等个人信息）
- ❌ 后端服务地址（localhost 仅本地有效）
- ❌ 飞书凭证（脚本不在部署范围）

### 公开可见的内容
- ✅ 策略名称和颜色配置
- ✅ ETF 代码（公开市场信息）
- ✅ 模拟/脱敏后的交易记录
- ✅ 复盘笔记（如包含在 review/ 中）

### 可选安全加固
如需隐藏复盘历史，取消 `.gitignore` 中 `review/` 的注释：
```gitignore
# 取消下行注释以排除复盘数据
review/
```

## 部署后验证
1. 打开 `https://你的用户名.github.io/quant-monitor/`
2. 确认主面板正常显示
3. 确认日期选择器可切换
4. 确认 "查看完整复盘" 链接可跳转
5. 确认无浏览器控制台报错

## 本地预览（部署前测试）
```bash
cd ~/三策略监控面板_项目档案/06_江予白_技术层
python3 -m http.server 8080
# 访问 http://localhost:8080
```
