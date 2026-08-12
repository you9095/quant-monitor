// ========== 三策略监控面板 · 数据层 ==========
// 数据schema + 模拟数据 + 轮询更新逻辑

const DataLayer = {
  // 数据源配置
  config: {
    pollInterval: 30000,      // 30秒轮询
    pricePollInterval: 5000,  // 5秒行情轮询
    apiBase: '/api/v1',  // 2026-08-11 改相对路径,Flask 8000 单端口同时 serve 静态 + API
    useMock: false            // 使用真实API（Mock服务器）
  },

  // 策略数据schema
  schema: {
    strategy: {
      id: 'string',           // qixing | r32 | zhuidian
      name: 'string',
      status: 'string',       // running | paused | error
      today_action: 'string', // BUY | SELL | REBALANCE | HOLD
      target: 'string',       // ETF代码
      position_pct: 'number', // 0-100
      cash: 'number',
      holdings: [{
        code: 'string',
        name: 'string',
        qty: 'number?',
        weight: 'number?',
        cost: 'number',
        price: 'number?',
        pnl: 'number?',
        pnl_pct: 'number?'
      }],
      metrics: {
        total_return: 'number?',
        sharpe: 'number?',
        max_drawdown: 'number?',
        trades_count: 'number',
        win_rate: 'number?'
      }
    },
    portfolio: {
      initial_capital: 'number',
      total_value: 'number',
      total_pnl: 'number',
      total_return_pct: 'number?',
      total_return: 'number?',
      last_update: 'string'   // ISO时间
    }
  },

  // 模拟数据（开发调试用）
  mockData: {
    strategies: [
      {
        id: 'qixing',
        name: '七星策略',
        status: 'running',
        today_action: 'DEFENSIVE',
        target: '511880',
        position_pct: 100.0,
        cash: 0.00,
        holdings: [
          // 2026-08-03 FIX_S3: holdings 换真实 signals positions (signals/qixing_2026-08-03.json)
          { code: '511880', name: '银华日利ETF', qty: 1000, weight: null, cost: 100.0, price: 100.0, pnl: null, pnl_pct: 0.0 }
        ],
        metrics: {
          total_return_2y: 32.35,
          max_dd_2y: -6.58,
          trades_2y: 40,
          // 2026-08-03 P0 fix: 实盘累计盈亏 (来自 signals/qixing_2026-08-03.json)
          live_total_pnl: -147.55,
          live_total_pnl_source_date: '2026-08-03',
          total_return_5y: null,
          max_dd_5y: null,
          trades_5y: null,
          annualized_return_2y: 32.35,
          annualized_return_5y: null,
          sharpe_2y: 2.15,
          sharpe_5y: null,
          calmar_2y: 4.92,
          signal_date: '2026-08-03',
          latest_round: 'R110_weekly_rebalance',
          latest_desc: '2Y年化32.35% 回撤-6.58% (R110_weekly_rebalance 最终基线)',
          trades_count: 40
        }
      },
      {
        id: 'r32',
        name: '三驾马车',
        status: 'running',
        today_action: 'HOLD',
        target: '512040',
        position_pct: 100.0,
        cash: 0,
        holdings: [
          // 2026-08-03 FIX_S3: holdings 换真实 signals positions (signals/r32_2026-08-03.json)
          { code: '512040', name: '512040', qty: 9900, weight: null, cost: 1.2226, price: 1.2226, pnl: null, pnl_pct: 0.0 }
        ],
        metrics: {
          total_return_2y: 114.08,
          max_dd_2y: -22.26,
          trades_2y: 29,
          total_return_5y: null,
          max_dd_5y: -3.0,
          trades_5y: null,
          annualized_return_2y: 17.16,
          annualized_return_5y: 19.6,
          sharpe_2y: 1.15,
          sharpe_5y: 1.5,
          // 2026-08-03 P0 fix: 实盘累计盈亏 (来自 signals/r32_2026-08-03.json)
          live_total_pnl: 3080.31,
          live_total_pnl_source_date: '2026-08-03',
          signal_date: '2026-08-03',
          latest_round: 'R35_rebal_15',
          latest_desc: '半月调仓 2Y年化17.16% 回撤-22.26% (R35)',
          trades_count: 29
        }
      },
      {
        id: 'zhuidian',
        name: '追电策略',
        status: 'running',
        today_action: 'HOLD',
        target: '513520',
        position_pct: 100.0,
        cash: 0,
        holdings: [
          // 2026-08-03 FIX_S3: holdings 换真实 signals positions (signals/zhuidian_2026-07-20.json, 11 只 qty=0 如实写入)
          { code: '513520', name: '513520', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '513100', name: '513100', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '518880', name: '518880', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '159985', name: '159985', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '513130', name: '513130', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '512890', name: '512890', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '161226', name: '161226', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '512100', name: '512100', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '159915', name: '159915', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '513030', name: '513030', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null },
          { code: '511010', name: '511010', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null }
        ],
        metrics: {
          total_return_2y: 288.06,
          max_dd_2y: -16.76,
          trades_2y: 63,
          total_return_5y: null,
          max_dd_5y: null,
          trades_5y: null,
          annualized_return_2y: 110.53,
          annualized_return_5y: null,
          sharpe_2y: 2.35,
          sharpe_5y: null,
          // 2026-08-03 P0 fix: 实盘累计盈亏 (来自 signals/zhuidian_2026-07-20.json)
          live_total_pnl: 27030.7,
          live_total_pnl_source_date: '2026-07-20',
          signal_date: '2026-07-20',
          latest_round: 'R17_score_max_38',
          latest_desc: '2Y年化110.53% 回撤-16.76% (R17_score_max_38)',
          trades_count: 63
        }
      },
      {
        id: 'sanhe',
        name: '三合策略 (Fusion)',
        status: 'running',
        today_action: 'REBALANCE',
        target: '588080',
        position_pct: 100.0,
        cash: 0,
        holdings: [
          // 2026-08-03 FIX_S3: holdings 换真实 signals positions (signals/sanhe_2026-08-03.json)
          { code: '588080', name: '588080', qty: 900, weight: null, cost: 2.18, price: 2.18, pnl: null, pnl_pct: 0.0 },
          { code: '510500', name: '510500', qty: 300, weight: null, cost: 8.913, price: 8.913, pnl: null, pnl_pct: 0.0 },
          { code: '512100', name: '512100', qty: 700, weight: null, cost: 3.498, price: 3.498, pnl: null, pnl_pct: 0.0 },
          { code: '510050', name: '510050', qty: 800, weight: null, cost: 3.035, price: 3.035, pnl: null, pnl_pct: 0.0 },
          { code: '159915', name: '159915', qty: 300, weight: null, cost: 3.859, price: 3.859, pnl: null, pnl_pct: 0.0 }
        ],
        metrics: {
          total_return_2y: 78.90,
          max_dd_2y: -23.40,
          trades_2y: 303,
          total_return_5y: 153.59,
          max_dd_5y: -24.96,
          trades_5y: 648,
          annualized_return_2y: 35.80,
          annualized_return_5y: 23.18,
          sharpe_2y: 1.44,
          sharpe_5y: 1.20,
          calmar_2y: 1.53,
          // 2026-08-03 P0 fix: 实盘累计盈亏 (来自 signals/sanhe_2026-08-03.json)
          live_total_pnl: 1874.57,
          live_total_pnl_source_date: '2026-08-03',
          signal_date: '2026-08-03',
          latest_round: 'R43_w_zhuidian_0.5',
          latest_desc: '历史2Y年化35.80% / 5Y年化23.18%',
          trades_count: 303
        }
      },
      {
        id: 'lightning',
        name: '闪电策略 (Lightning)',
        status: 'running',
        today_action: 'REBALANCE',
        target: '513520',
        position_pct: 100.0,
        cash: 0,
        holdings: [
          // 2026-08-03 FIX_S3: holdings 换真实 signals positions (signals/lightning_2026-08-03.json, 1 只 qty=0 如实写入)
          { code: '513520', name: '513520', qty: 0, weight: null, cost: 0.0, price: 0.0, pnl: null, pnl_pct: null }
        ],
        metrics: {
          total_return_2y: 74.06,
          max_dd_2y: -14.06,
          trades_2y: 323,
          total_return_5y: null,
          max_dd_5y: null,
          trades_5y: null,
          annualized_return_2y: 27.34,
          annualized_return_5y: null,
          sharpe_2y: 1.20,
          sharpe_5y: null,
          calmar_2y: 1.94,
          // 2026-08-03 P0 fix: 实盘累计盈亏 (来自 signals/lightning_2026-08-03.json)
          live_total_pnl: 4712.3,
          live_total_pnl_source_date: '2026-08-03',
          signal_date: '2026-08-03',
          latest_round: 'R4_m3',
          latest_desc: '2Y年化27.34%（5Y未跑）',
          trades_count: 323
        }
      }
    ],
    portfolio: {
      // 2026-08-03 修复: 组合总览接真值 — total_pnl=5 策略 signals 最新 live_total_pnl 求和
      // (qixing -147.55 + r32 3080.31 + zhuidian 27030.7 + sanhe 1874.57 + lightning 4712.3 = 36550.33)
      initial_capital: 50000,
      total_value: 86550.33,
      total_pnl: 36550.33,
      total_return_pct: 73.10,
      total_return: null,
      last_update: new Date().toISOString()
    },
    // 历史收益曲线数据
    history: {
      '2y': {
        labels: ['2024-06','2024-07','2024-08','2024-09','2024-10','2024-11','2024-12','2025-01','2025-02','2025-03','2025-04','2025-05','2025-06','2025-07','2025-08','2025-09','2025-10','2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05','2026-06'],
        qixing: [0, -8, -12, -5, 0, 8, 15, 22, 18, 12, 8, 5, -2, 5, 10, 18, 25, 30, 35, 38, 42, 48, 50, 52, 74.0],
        qixing_5y: [0, -5, -3, 2, 5, 8, 12, 15, 10, 15, 18, 22, 25, 28, 30, 32, 32, 32, 32, 32, 32.35, 32, 32, 32, 32.35],
        r32: [0, 2.1, 4.5, 5.2, 3.8, 7.2, 12.0, 10.5, 8.2, 8.0, 12.5, 18.2, 25.0, 23.5, 28.0, 30.2, 28.5, 25.0, 22.0, 26.5, 30.0, 35.0, 33.2, 36.5, 38.14],
        sanhe: [0, 1.5, 3.0, 4.2, 5.0, 8.0, 12.5, 10.0, 8.5, 11.0, 15.0, 22.0, 28.0, 26.0, 30.0, 33.0, 31.0, 28.0, 32.0, 38.0, 45.0, 52.0, 56.0, 65.0, 78.90],
        zhuidian: [0, 5, 12, 18, 25, 32, 40, 45, 50, 58, 68, 80, 92, 105, 125, 140, 160, 180, 210, 250, 260, 270, 278, 285, 288.06],
        lightning: [0, 3, 6, 4, 8, 12, 10, 14, 18, 15, 20, 25, 30, 28, 35, 40, 38, 45, 50, 55, 60, 65, 68, 72, 74.06]
      },
      '5y': {
        labels: ['2021-06','2021-09','2021-12','2022-03','2022-06','2022-09','2022-12','2023-03','2023-06','2023-09','2023-12','2024-03','2024-06','2024-09','2024-12','2025-03','2025-06','2025-09','2025-12','2026-03','2026-06'],
        qixing: [0, -5, -3, 2, 5, 8, 12, 15, 10, 15, 18, 22, 25, 28, 30, 32, 32, 32, 32, 32, 32.35, 32, 32, 32, 32.35],
        r32: [0, 2, 5, 12, 18, 25, 38, 45, 52, 65, 78, 92, 105, 118, 125, 132, 138, 145, 152, 158, 114.08],
        sanhe: [0, 3, 8, 12, 10, 5, -2, 0, 8, 15, 25, 35, 50, 62, 75, 90, 105, 120, 135, 148, 153.59],
        zhuidian: [0, 10, 25, 15, 5, -8, -5, 10, 20, 35, 50, 70, 95, 130, 170, 200, 225, 240, 248, 252, 256.18]
      }
    }
  },

  // 本地存储
  storage: {
    get(key) {
      try { return JSON.parse(localStorage.getItem('quant_' + key)); } catch { return null; }
    },
    set(key, value) {
      localStorage.setItem('quant_' + key, JSON.stringify(value));
    }
  },

  // 获取数据（模拟/API切换）
  async fetchStrategies() {
    // 始终优先调用真实API（real_data_server）
    console.log('[2026-08-09 DEBUG] fetchStrategies called, apiBase=', this.config.apiBase);
    try {
      const res = await fetch(`${this.config.apiBase}/dashboard/overview`);
      console.log('[DEBUG] fetch res status=', res.status, 'ok=', res.ok);
      const result = await res.json();
      console.log('[DEBUG] fetch result code=', result?.code, 'strategies=', result?.data?.strategies?.length);
      if (result.code === 0) {
        return this.transformApiData(result.data);
      }
      throw new Error(result.message);
    } catch (err) {
      console.error('API获取失败，回退到模拟数据:', err);
      // 模拟微小波动
      const data = JSON.parse(JSON.stringify(this.mockData));
      data.strategies.forEach(s => {
        s.holdings.forEach(h => {
          if (h.price && h.cost) {
            // 2026-08-03 修复 (P1-6): 移除 Math.random 价格 jitter(每次刷新生成随机假盈亏);
            // pnl 仅在 qty 存在时可确算, 无 qty 持仓(weight 语义)保持 null, 禁止编造
            h.pnl = h.qty != null ? +((h.price - h.cost) * h.qty).toFixed(2) : null;
            // FIX_S3: cost=0 (空仓) 时 (price/cost-1) 为 NaN → 保持 null, 禁止 NaN 上屏
            h.pnl_pct = h.cost > 0 ? +((h.price / h.cost - 1) * 100).toFixed(2) : null;
          }
        });
      });
      data.portfolio.last_update = new Date().toISOString();
      return data;
    }
  },

  // API数据格式转换
  transformApiData(apiData) {
    const strategies = apiData.strategies.map(s => ({
      id: s.strategy_id,
      name: s.strategy_name,
      status: s.status,
      today_action: s.today_action || 'HOLD',
      position_pct: s.position_ratio ? s.position_ratio * 100 : 0,
      cash: s.cash || 0,
      total_asset: s.total_asset,
      total_return: s.total_return,
      today_pnl: s.today_pnl,
      today_return: s.today_return,
      holdings: (s.positions || s.holdings || []).map(p => ({
        code: p.code,
        name: p.name,
        qty: p.quantity,
        weight: p.weight ? (p.weight * 100).toFixed(0) : null,
        cost: p.cost_price,
        price: p.current_price,
        pnl: p.pnl,
        pnl_pct: p.pnl_pct
      })),
      metrics: {
        total_return: s.total_return,
        sharpe: s.sharpe_ratio,
        max_drawdown: s.max_drawdown,
        annual_volatility: s.annual_volatility,
        trades_count: s.trades_count || 0,
        win_rate: s.win_rate,
        // 三层标签（v2.0 路线图 P0-4）
        version_tag: s.version_tag || null,
        data_period: s.data_period || null,
        caliber: s.caliber || null,
        signal_date: s.signal_date || null
      }
    }));

    const totalValue = strategies.reduce((sum, s) => sum + (s.total_asset || 0), 0);
    const combinedReturn = apiData.combined ? apiData.combined.total_return : null;

    return {
      strategies,
      portfolio: {
        total_value: totalValue,
        total_return: combinedReturn,
        last_update: apiData.update_time
      }
    };
  },

  // 轮询定时器
  pollTimer: null,
  priceTimer: null,

  // 启动轮询
  startPolling(callback) {
    this.stopPolling();
    const poll = async () => {
      const data = await this.fetchStrategies();
      this.storage.set('lastData', data);
      if (callback) callback(data);
    };
    poll(); // 立即执行一次
    this.pollTimer = setInterval(poll, this.config.pollInterval);
  },

  // 停止轮询
  stopPolling() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    if (this.priceTimer) { clearInterval(this.priceTimer); this.priceTimer = null; }
  },

  // 获取缓存数据
  getCachedData() {
    return this.storage.get('lastData') || this.mockData;
  }
};

// 导出
if (typeof module !== 'undefined') module.exports = DataLayer;