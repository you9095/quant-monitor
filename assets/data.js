// ========== 三策略监控面板 · 数据层 ==========
// 数据schema + 模拟数据 + 轮询更新逻辑

const DataLayer = {
  // 数据源配置
  config: {
    pollInterval: 30000,      // 30秒轮询
    pricePollInterval: 5000,  // 5秒行情轮询
    apiBase: 'http://localhost:8000/api/v1',  // Mock API基地址
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
        today_action: 'BUY',
        target: '159915',
        position_pct: 99.88,
        cash: 117.40,
        holdings: [
          { code: '159915', name: '创业板ETF', qty: 25100, cost: 3.977, price: 3.985, pnl: 200.80, pnl_pct: 0.20 }
        ],
        metrics: { total_return: null, sharpe: null, max_drawdown: null, trades_count: 1, win_rate: null }
      },
      {
        id: 'r32',
        name: '三驾马车 R32',
        status: 'running',
        today_action: 'REBALANCE',
        target: null,
        position_pct: 99.40,
        cash: 598.59,
        holdings: [
          { code: '159967', name: '国企红利', weight: 20, cost: 0.995, price: 1.002, pnl: 70.35, pnl_pct: 0.70 },
          { code: '513100', name: '纳指ETF', weight: 20, cost: 2.205, price: 2.218, pnl: 117.60, pnl_pct: 0.59 },
          { code: '513520', name: '日经ETF', weight: 20, cost: 1.346, price: 1.338, pnl: -59.20, pnl_pct: -0.59 },
          { code: '159915', name: '创业板', weight: 20, cost: 3.977, price: 3.985, pnl: 40.16, pnl_pct: 0.20 },
          { code: '513500', name: '标普500', weight: 20, cost: 2.179, price: 2.191, pnl: 54.48, pnl_pct: 0.55 }
        ],
        metrics: {
          total_return_2y: 38.14,
          max_dd_2y: -9.16,
          trades_2y: 8,
          total_return_5y: 19.60,
          max_dd_5y: -39.71,
          trades_5y: 73,
          annualized_return_2y: 19.05,
          annualized_return_5y: 19.60,
          sharpe: 1.42
        }
      },
      {
        id: 'zhuidian',
        name: '追电策略',
        status: 'running',
        today_action: 'BUY',
        target: '513100',
        position_pct: 99.95,
        cash: 53.56,
        holdings: [
          { code: '513100', name: '纳指ETF', qty: 45300, cost: 2.205, price: 2.218, pnl: 588.90, pnl_pct: 0.59 }
        ],
        metrics: {
          total_return_2y: 288.06,
          max_dd_2y: -16.76,
          trades_2y: 63,
          total_return_5y: 256.18,
          max_dd_5y: -21.15,
          trades_5y: 132,
          annualized_return_2y: 103.18,
          annualized_return_5y: 32.65,
          sharpe_2y: 2.35,
          sharpe_5y: 1.18,
          calmar_2y: 6.60,
          calmar_5y: 1.54,
          sharpe: 2.35,
          latest_round: 'R17_score_max_3.8',
          latest_desc: '加权回归动量+持仓1+周度调仓'
        }
      },
      {
        id: 'sanhe',
        name: '三合策略 (Fusion)',
        status: 'running',
        today_action: 'REBALANCE',
        target: null,
        position_pct: 98.40,
        cash: 161.46,
        holdings: [
          { code: '513100', name: '纳指ETF', weight: 20, cost: 2.205, price: 2.218, pnl: 11.7, pnl_pct: 0.59 },
          { code: '518880', name: '黄金ETF', weight: 20, cost: 4.620, price: 4.658, pnl: 15.96, pnl_pct: 0.82 },
          { code: '159985', name: '豆粕ETF', weight: 20, cost: 1.040, price: 1.052, pnl: 22.8, pnl_pct: 1.15 },
          { code: '511010', name: '国债ETF', weight: 20, cost: 1.378, price: 1.381, pnl: 4.29, pnl_pct: 0.22 },
          { code: '512890', name: '红利低波ETF', weight: 20, cost: 1.185, price: 1.198, pnl: 21.56, pnl_pct: 1.10 }
        ],
        metrics: {
          total_return_2y: 83.0,
          max_dd_2y: -23.38,
          trades_2y: 40,
          total_return_5y: 105.31,
          max_dd_5y: -21.80,
          trades_5y: 693,
          annualized_return_2y: 35.15,
          annualized_return_5y: 17.48,
          sharpe_2y: 1.50,
          sharpe_5y: 0.97,
          calmar_2y: 1.50,
          calmar_5y: 0.80,
          sharpe: 1.50,
          latest_round: 'R25_vol_weight',
          latest_desc: '三策略融合+波动率倒数加权'
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
          { code: '513100', name: '纳指ETF', weight: 25, cost: 2.205, price: 2.218, pnl: 5.85, pnl_pct: 0.59 },
          { code: '513520', name: '日经ETF', weight: 25, cost: 1.346, price: 1.358, pnl: 8.76, pnl_pct: 0.89 },
          { code: '513030', name: '德国ETF', weight: 25, cost: 1.440, price: 1.452, pnl: 16.68, pnl_pct: 0.83 },
          { code: '513130', name: '恒生科技ETF', weight: 25, cost: 0.404, price: 0.412, pnl: 39.6, pnl_pct: 1.98 }
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
          calmar_2y: 1.94,
          sharpe: 1.20,
          latest_round: 'R4_m3',
          latest_desc: '3日动量+4只跨境+止盈止损'
        }
      }
    ],
    portfolio: {
      total_value: 50000,
      total_return: null,
      last_update: new Date().toISOString()
    },
    // 历史收益曲线数据
    history: {
      '2y': {
        labels: ['2024-06','2024-07','2024-08','2024-09','2024-10','2024-11','2024-12','2025-01','2025-02','2025-03','2025-04','2025-05','2025-06','2025-07','2025-08','2025-09','2025-10','2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05','2026-06'],
        r32: [0, 2.1, 4.5, 5.2, 3.8, 7.2, 12.0, 10.5, 8.2, 8.0, 12.5, 18.2, 25.0, 23.5, 28.0, 30.2, 28.5, 25.0, 22.0, 26.5, 30.0, 35.0, 33.2, 36.5, 38.14],
        sanhe: [0, 1.5, 3.0, 4.2, 5.0, 8.0, 12.5, 10.0, 8.5, 11.0, 15.0, 22.0, 28.0, 26.0, 30.0, 33.0, 31.0, 28.0, 32.0, 38.0, 45.0, 52.0, 56.0, 65.0, 83.0],
        zhuidian: [0, 5, 12, 18, 25, 32, 40, 45, 50, 58, 68, 80, 92, 105, 125, 140, 160, 180, 210, 250, 260, 270, 278, 285, 288.06],
        lightning: [0, 3, 6, 4, 8, 12, 10, 14, 18, 15, 20, 25, 30, 28, 35, 40, 38, 45, 50, 55, 60, 65, 68, 72, 74.06]
      },
      '5y': {
        labels: ['2021-06','2021-09','2021-12','2022-03','2022-06','2022-09','2022-12','2023-03','2023-06','2023-09','2023-12','2024-03','2024-06','2024-09','2024-12','2025-03','2025-06','2025-09','2025-12','2026-03','2026-06'],
        r32: [0, 5.2, 8.5, 2.1, -5.8, -12.3, -8.5, -2.1, 3.5, 8.2, 12.5, 15.8, 18.2, 15.5, 12.0, 8.5, 15.2, 18.5, 10.2, 15.8, 19.60],
        sanhe: [0, 8, 15, 5, -3, -10, -5, 5, 12, 18, 25, 35, 50, 45, 55, 65, 75, 85, 92, 100, 105.31],
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
        win_rate: s.win_rate
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
