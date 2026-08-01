// ========== 三策略监控面板 · 数据层 ==========
// 数据schema + 模拟数据 + 轮询更新逻辑

const DataLayer = {
  // 数据源配置
  config: {
    pollInterval: 30000,      // 30秒轮询
    pricePollInterval: 5000,  // 5秒行情轮询
    apiBase: '/api/v1',  // API基地址（Docker/任意端口通用）
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
      total_value: 'number',
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
        today_action: 'REBALANCE',
        target: '159915',
        position_pct: 99.9,
        cash: 50.00,
        holdings: [
          { code: '159915', name: '创业板ETF', qty: 1350, cost: 4.02, price: 4.15, pnl: 195.00, pnl_pct: 3.23 }
        ],
        metrics: {
          total_return_2y: 74.0,
          max_dd_2y: -6.58,
          trades_2y: 40,
          total_return_5y: 8.85,
          max_dd_5y: -2.43,
          trades_5y: 523,
          annualized_return_2y: 32.35,
          annualized_return_5y: 1.92,
          sharpe_2y: 2.15,
          sharpe_5y: 0.57,
          calmar_2y: 4.92,
          latest_round: 'R120_breadth_0.353_holdings_1',
          latest_desc: '2Y年化32.35% 5Y年化1.92% (R11_weekly_2最优)'
        }
      },
      {
        id: 'r32',
        name: '三驾马车',
        status: 'running',
        today_action: 'REBALANCE',
        target: null,
        position_pct: 100.0,
        cash: 0,
        holdings: [
          { code: '159967', name: '国企红利', weight: 16.67, cost: 0.995, price: 1.00, pnl: 100.00, pnl_pct: 0.67 },
          { code: '513100', name: '纳指ETF', weight: 16.67, cost: 2.205, price: 2.22, pnl: 180.00, pnl_pct: 0.68 },
          { code: '513520', name: '日经ETF', weight: 16.67, cost: 1.346, price: 1.35, pnl: 120.00, pnl_pct: 0.93 },
          { code: '159915', name: '创业板', weight: 16.67, cost: 3.977, price: 3.99, pnl: 130.00, pnl_pct: 0.33 },
          { code: '513500', name: '标普500', weight: 16.67, cost: 2.179, price: 2.19, pnl: 140.00, pnl_pct: 0.50 },
          { code: '518880', name: '黄金ETF', weight: 16.67, cost: 4.620, price: 4.66, pnl: 80.00, pnl_pct: 0.87 }
        ],
        metrics: {
          total_return_2y: 114.08,
          max_dd_2y: -22.26,
          trades_2y: 29,
          total_return_5y: 158.64,
          max_dd_5y: -25.48,
          trades_5y: 648,
          annualized_return_2y: 17.16,
          annualized_return_5y: 23.72,
          sharpe_2y: 1.15,
          sharpe_5y: 1.19,
          latest_round: 'R35_rebal_15',
          latest_desc: '半月调仓 2Y年化17.16% 5Y年化23.72%'
        }
      },
      {
        id: 'zhuidian',
        name: '追电策略',
        status: 'running',
        today_action: 'REBALANCE',
        target: '513100,513520',
        position_pct: 100.0,
        cash: 0,
        holdings: [
          { code: '513100', name: '纳指ETF', qty: 1820, cost: 2.18, price: 2.22, pnl: 670.00, pnl_pct: 1.79 },
          { code: '513520', name: '日经ETF', qty: 980, cost: 2.05, price: 2.10, pnl: 490.00, pnl_pct: 2.44 },
          { code: '513500', name: '标普500', qty: 1150, cost: 2.35, price: 2.38, pnl: 455.00, pnl_pct: 1.28 }
        ],
        metrics: {
          total_return_2y: 288.06,
          max_dd_2y: -16.76,
          trades_2y: 63,
          total_return_5y: 256.18,
          max_dd_5y: -21.15,
          trades_5y: 132,
          annualized_return_2y: 110.53,
          annualized_return_5y: 32.65,
          sharpe_2y: 2.35,
          sharpe_5y: 1.18,
          latest_round: 'R17_score_max_38',
          latest_desc: '2Y年化110.53% 5Y年化32.65%'
        }
      },
      {
        id: 'sanhe',
        name: '三合策略 (Fusion)',
        status: 'running',
        today_action: 'REBALANCE',
        target: null,
        position_pct: 100.0,
        cash: 0,
        holdings: [
          { code: '513100', name: '纳指ETF', weight: 24.18, cost: 2.205, price: 2.22, pnl: 180.00, pnl_pct: 0.68 },
          { code: '518880', name: '黄金ETF', weight: 24.18, cost: 4.620, price: 4.66, pnl: 220.00, pnl_pct: 0.87 },
          { code: '159985', name: '豆粕ETF', weight: 24.18, cost: 1.040, price: 1.05, pnl: 95.00, pnl_pct: 0.96 },
          { code: '511010', name: '国债ETF', weight: 24.18, cost: 1.378, price: 1.38, pnl: 55.00, pnl_pct: 0.14 }
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
          latest_round: 'R44_weekly_h4_cap2418',
          latest_desc: '历史2Y年化35.80% / 5Y年化23.18%'
        }
      },
      {
        id: 'lightning',
        name: '闪电策略 (Lightning)',
        status: 'running',
        today_action: 'REBALANCE',
        target: null,
        position_pct: 100.0,
        cash: 0,
        holdings: [
          { code: '513100', name: '纳指ETF', weight: 25, cost: 2.205, price: 2.22, pnl: 180.00, pnl_pct: 0.68 },
          { code: '513520', name: '日经ETF', weight: 25, cost: 1.346, price: 1.35, pnl: 95.00, pnl_pct: 0.93 },
          { code: '513030', name: '德国ETF', weight: 25, cost: 1.440, price: 1.45, pnl: 110.00, pnl_pct: 0.71 },
          { code: '513130', name: '恒生科技ETF', weight: 25, cost: 0.404, price: 0.412, pnl: 160.00, pnl_pct: 1.98 }
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
          latest_round: 'R4_m3',
          latest_desc: '2Y年化27.34%（5Y未跑）'
        }
      }
    ],
    portfolio: {
      total_value: 50000,
      total_return: null,
      total_pnl: 0,
      total_return_pct: 0,
      initial_capital: 50000,
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
    try {
      const res = await fetch(`${this.config.apiBase}/dashboard/overview`);
      const result = await res.json();
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
          if (h.price) {
            h.price = +(h.price * (1 + (Math.random() - 0.5) * 0.002)).toFixed(3);
            h.pnl = +((h.price - h.cost) * (h.qty || 20000)).toFixed(2);
            h.pnl_pct = +((h.price / h.cost - 1) * 100).toFixed(2);
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
      holdings: (s.positions || []).map(p => ({
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