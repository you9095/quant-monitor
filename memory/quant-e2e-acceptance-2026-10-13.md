# 记忆：端到端验收通过 + 全自动闭环（2026-10-13）

- **最高指令回归**：所有调试/测试/检测/验收全部在 macOS 完成，跑通后才 push GitHub、再由 Windows 同步；不再在 Windows 生产机症状驱动打补丁。
- **后端启动卡死根因**：launchd 默认 `ProcessType=Standard` 对守护进程 I/O 节流，主线程 read 信号文件被推迟数十秒（手动进程读 459 个文件仅 0.12 秒）。plist 改 `ProcessType=Interactive` 后 **6 秒 bind**。该 plist 在 `~/Library`、不在仓库。
- **盈亏历史漏算**：空仓/无历史策略（三驾马车、黄金组合A各持现金1万）缺 daily 快照被聚合漏算 20000 元；`live_aggregator.build_pnl_history` 加 forward-fill 修复。
- **历史K线假重试**：`market_data.load_etf_close` 首次失败即 `return []`（实际只试1次），网络波动导致 r32/goldcombo 偶发 no_history；改为真正重试3次、全失败才兜底旧缓存。
- **验收结果**：四套测试 71 项全绿；真实浏览器两首页隔离（实盘 -688.75 vs 模拟 +27761）、对账单 6/6、买卖记录14笔分页10行、盈亏历史三Tab正常。
- **全自动闭环**：双击桌面"AI量化面板"→ `launch_panel.py --open` 六步（三通道更新代码→起后台→补注册→guard成交→上传→心跳→开面板）。QuantTradeGuard 动作 `trade_supervisor.py --guard`，登录后每10分钟 + 工作日15:00每2分钟/30分 + 15:30每10分钟/2小时。
- **提交**：代码远程 master = `0e24507`（5个逻辑提交：98bd26b/98622d7/6b7a0f5/415fa56/0e24507）；数据真相 `d815f21`。
- **教训**：① 在 Mac 手动跑引擎会写真 live-data 且非交易时段用前日价，调试应走临时账本；跑完务必查 live-data status，污染即 `git restore` + 删未跟踪 daily、绝不 push。② 排障先做"手动 vs 守护进程对照"，能快速定位 launchd I/O 节流类问题。③ 看代码要核对"注释承诺 vs 实际调用"（MARKET_CLOSE 实际在 guard_once 第566行生效，非主循环缺失）。
