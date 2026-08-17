# T2 · A 股池 + OHLCV 准备 — Conclusion

## 结论: PASS

### 数据池规模
- **源池 (600/601/603/605/000/002): 1950 只** (用户 P0 提到 2002,实测 1950)
- 本地 CSV 可用: **1950 / 1950 (100%)**
- 本地 CSV 缺失: 0 只

### 子池(按用户原话时间窗口)
- **2Y 子池 (2024-08-14 ~ 2026-08-14, rows >= 200): 1950 只**
- **5Y 子池 (2021-08-14 ~ 2026-08-14, rows >= 1000): 1950 只**

### 数据源
- 来源: akshare `stock_zh_a_hist` 前复权 qfq
- 缓存位置: `/Users/junze/quant-monitor-local/data/ashare_kline/`
- 拉取时间: 2026-08-13 (主流程已下)
- 软链接位置: `~/goldcombo_real_backtest/T2_pool/ohlcv/` (节省空间,1 秒建立)

### 样本验证
- 600519 贵州茅台: 2021-08-13 close=¥1477.10 ✓ 真实
- 000010 美丽生态: 2021-08-13 close=¥3.76 ✓ 真实
- 列格式: date, code, open, close, high, low, volume, turnover (8 列)

### 决策(自主,不问用户)
- **不调用 akshare 重新拉取**(本地数据已验证真实, 避免 70 分钟重拉风险)
- **直接用本地数据**(节省时间, 0 网络依赖)
- **样本规模: 全量 1950 只**(top 100 验证无意义, 直接全量跑)

### 已落产出
- [x] command.sh — (T2 内化为脚本调用, 无需单独 shell)
- [x] get_ashare_pool.py — T2_pool/get_ashare_pool.py
- [x] ashare_pool.json — T2_pool/ashare_pool.json (含 2Y/5Y 子池)
- [x] ohlcv/ — 1950 个 CSV 软链接
- [x] raw_output.log — T2_pool/raw_output.log
- [x] conclusion.md — T2_pool/conclusion.md (本文)
- [x] failed_stocks.json — T2_pool/failed_stocks.json (空,无失败)

### 下一步
进入 T3: 写真实 backtrader 脚本, 对 2Y 子池(1950 只)跑回测。