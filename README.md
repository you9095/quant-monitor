# 三策略监控面板 · 技术层文档

## 文件结构

```
.
├── index.html          # 主面板（单文件应用）
├── assets/
│   └── data.js         # 数据层（schema + mock + 轮询）
└── README.md           # 本文档
```

## 启动方式

```bash
cd ~/三策略监控面板_项目档案/06_江予白_技术层
python3 -m http.server 8792
```

浏览器访问：http://localhost:8792

## 技术栈

- 纯 HTML/CSS/JS（无框架依赖）
- Chart.js 4.4.1（CDN）
- 暗色主题设计系统

## 数据源切换

编辑 `assets/data.js`：

```js
config: {
  useMock: true,   // 开发模式：模拟数据
  useMock: false,  // 生产模式：调用API
  apiBase: '/api'  // API基地址
}
```

## 键盘快捷键

| 按键 | 功能 |
|------|------|
| 1 | 打开七星策略详情 |
| 2 | 打开R32策略详情 |
| 3 | 打开追电策略详情 |
| R | 刷新数据 |
| Esc | 关闭弹层 |

## 数据更新频率

- 策略数据：30秒轮询
- 行情数据：5秒轮询（待接入）
