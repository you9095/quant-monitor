# T1 · 数据源 + backtrader 环境核查 — Conclusion

## 结论: PASS

### 环境验证
- Python: /opt/local/bin/python3.12 (3.12.13)
- backtrader: 1.9.78.123 (从清华镜像安装成功,SSL 通道正常)
- pandas: 3.0.3, numpy: 2.4.3
- akshare: 1.18.64 (用户 Downloads 备份外另有本地 OHLCV)

### 数据源验证 (核心发现)
**本地已有真实 A 股 OHLCV 数据(2026-08-13 由主流程下载)**
- 路径: `/Users/junze/quant-monitor-local/data/ashare_kline/`
- 文件数: 2033 个 CSV (date,code,open,close,high,low,volume,turnover)
- 数据期: 2021-08-13 ~ 2026-08-13 (5Y 完整)
- 样本验证: 000010 美丽生态(¥3.76)、600519 贵州茅台(¥1477.10) 数据真实可信
- 来源: akshare `stock_zh_a_hist` 前复权 qfq

### A 股池清单
- 路径: `/Users/junze/quant-monitor-local/data/ashare_pool.json`
- 过滤规则: 600xxx/601xxx/603xxx/605xxx/000xxx/002xxx (排除 688 科创 + 300 创业 + 4xx/8xx)
- 池大小: 1950 只 (与用户 P0 提到的 2002 略有差异,实测为 1950)

### 数据质量过滤后池子(ashare_filter_summary.json)
- 过滤逻辑: rows >= 1000 AND avg(turnover) >= 1e7 (5Y 完整 + 流动性)
- 通过: 1950 只 (1:1,所有池都通过)
- 时间戳: 2026-08-14 08:24:20 (今日)

### 决策
**使用本地 OHLCV 数据直接回测,不调用 akshare(避免重复拉取 + 网络风险)**
- T2: 不需要重新拉数据,直接复用 `data/ashare_kline/`
- T2 任务目标改为"用本地数据确认 2Y/5Y 时间窗有效股票清单"

### 已落产出
- [x] command.sh — T1_setup/command.sh
- [x] raw_output.log — T1_setup/raw_output.log
- [x] conclusion.md — T1_setup/conclusion.md (本文)

### 下一步
进入 T2: 复制 1950 只股票 OHLCV 到 `T2_pool/ohlcv/`, 生成 2Y/5Y 子池清单。