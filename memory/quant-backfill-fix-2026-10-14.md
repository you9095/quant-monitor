# 记忆：补记链路崩溃修复 + 多源历史K线 + 自动更新闭环实战（2026-10-14）

- **自动更新闭环首次实战成功**：Windows 开机双击桌面图标后，经 GitHub 自动拉取最新代码（心跳 code_commit 从 f204e22 变 0c86d2a），无人肉下载、无命令行。代码更新只在 `launch_panel.py` STEP 1（fetch + reset --hard，更新后自动 relaunch 自身）；计划任务 QuantTradeGuard 跑 `trade_supervisor.py --guard`、**不更新代码**。
- **补记崩溃根因一（P0）**：`backfill_day.py` 调 `eng.load_hist_klines(code, day, n=60)`，但 `run_daily_engine.py` 无此函数（只有 `load_hist_map` 返回纯价格 dict），抛 `AttributeError` 被 pythonw 静默吞掉，守护崩溃。
- **补记崩溃根因二（P0）**：`backfill_one` 用 `hist_map/quote_map/backfill` 三参数调 `run_once`，但主流程重写（98bd26b）后签名不接受，报 `TypeError: unexpected keyword argument 'hist_map'`。修复后 run_once 签名含这三个补记参数，补记用预取真实收盘价并写 `is_backfill/data_nature` 标注。
- **东财历史接口持续断连**：159915/159967/510300/513500/588080 等经 akshare `fund_etf_hist_em` 持续 RemoteDisconnected（非代理、非临时）。在 `market_data.py` 新增 `sina_etf_hist/tencent_etf_hist/load_hist_klines_multi`（东财缓存→东财→新浪→腾讯，只取补记日及之前）。今日成交价源为 tencent 即多源兜底生效。
- **数据（已核对连续性）**：10-13 事后补记（2笔，闪电），10-14 正常成交（2笔，闪电）；六策略总资产 59341.09、总盈亏 -658.91（-1.10%），5 个交易日，最大回撤 -1.49%。闪电 9854.85→9974.42、追电 9989.23→10090.03。
- **版本**：代码远程 master = `0c86d2a`（仅 2 文件：api/market_data.py、run_daily_engine.py）；数据仓库 HEAD = `6f714a8`。
- **遗留**：工作区 6 个非本轮有意改动（bridge_worklog_to_signal.py、goldcombo baseline + 4 report）未提交、保留待判来源。
- **教训**：① 主流程重写后必须同步核对所有调用方（backfill/supervisor/launcher）签名，否则留静默崩溃；② pythonw 静默吞错，关键异常必须进日志；③ 行情至少 3 独立源（东财/新浪/腾讯），补记只取补记日及之前防未来数据；④ 调试走临时账本（/tmp/qtest_clean），不污染真 live-data。
- **日常**：每个交易日双击桌面"AI量化面板"图标即全自动；全程模拟盘、本机真实撮合，不接券商真实/资金账号。
