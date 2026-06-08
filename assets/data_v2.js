// ========== 三策略监控面板 · 数据层 V2.0 ==========
// 动态策略支持：策略数量由后端配置决定，前端自适应渲染

const DataLayer = {
  config: {
    pollInterval: 30000,
    pricePollInterval: 5000,
    apiBase: 'http://localhost:8000/api/v1',
    useMock: false
  },

  // 缓存策略配置（从 /api/v1/strategies 获取）
  strategyConfig: null,

  // 获取策略配置
  async fetchStrategyConfig() {
    try {
      const res = await fetch(`${this.config.apiBase}/strategies`);
      const result = await res.json();
      if (result.code === 0) {
        this.strategyConfig = result.data.strategies;
        return this.strategyConfig;
      }
    } catch (err) {
      console.error('获取策略配置失败:', err);
    }
    // 默认回退
    this.strategyConfig = [
      { strategy_id: 'qixing', strategy_name: '七星策略', color: '#3b82f6' },
      { strategy_id: 'r32', strategy_name: '三驾马车R32', color: '#10b981' },
      { strategy_id: 'zhuidian', strategy_name: '追电策略', color: '#f59e0b' }
    ];
    return this.strategyConfig;
  },

  // 获取策略颜色映射
  getStrategyColors() {
    if (!this.strategyConfig) return {};
    const colors = {};
    this.strategyConfig.forEach(s => {
      colors[s.strategy_id] = s.color;
    });
    return colors;
  },

  async fetchStrategies() {
    try {
      // 并行获取策略配置和概览数据
      const [configRes, overviewRes] = await Promise.all([
        fetch(`${this.config.apiBase}/strategies`),
        fetch(`${this.config.apiBase}/dashboard/overview`)
      ]);

      const configResult = await configRes.json();
      const overviewResult = await overviewRes.json();

      if (configResult.code === 0) {
        this.strategyConfig = configResult.data.strategies;
      }

      if (overviewResult.code === 0) {
        return this.transformApiData(overviewResult.data);
      }
      throw new Error(overviewResult.message);
    } catch (err) {
      console.error('API获取失败:', err);
      return this.getMockData();
    }
  },

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
      holdings: (s.holdings || []).map(p => ({
        code: p.code,
        name: p.name,
        qty: p.quantity,
        weight: p.weight ? p.weight.toFixed(0) : null,
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

  // 动态生成Mock数据（根据策略配置数量）
  getMockData() {
    const configs = this.strategyConfig || [
      { strategy_id: 'qixing', strategy_name: '七星策略', color: '#3b82f6' },
      { strategy_id: 'r32', strategy_name: '三驾马车R32', color: '#10b981' },
      { strategy_id: 'zhuidian', strategy_name: '追电策略', color: '#f59e0b' }
    ];

    const strategies = configs.map(cfg => ({
      id: cfg.strategy_id,
      name: cfg.strategy_name,
      status: 'running',
      today_action: 'HOLD',
      position_pct: 0,
      cash: 10000,
      total_asset: 10000,
      total_return: 0,
      today_pnl: 0,
      today_return: 0,
      holdings: [],
      metrics: { total_return: 0, trades_count: 0 }
    }));

    return {
      strategies,
      portfolio: {
        total_value: strategies.reduce((s, x) => s + x.total_asset, 0),
        total_return: 0,
        last_update: new Date().toISOString()
      }
    };
  },

  // 获取净值曲线（动态策略数量）
  async fetchNavCurves() {
    try {
      const res = await fetch(`${this.config.apiBase}/dashboard/nav_curves`);
      const result = await res.json();
      if (result.code === 0) {
        return result.data;
      }
      throw new Error(result.message);
    } catch (err) {
      console.error('净值曲线获取失败:', err);
      return { curves: {}, today: new Date().toISOString().split('T')[0] };
    }
  },

  // 获取单个策略详情
  async fetchStrategyDetail(sid) {
    try {
      const [posRes, actionRes] = await Promise.all([
        fetch(`${this.config.apiBase}/${sid}/positions`),
        fetch(`${this.config.apiBase}/${sid}/today_actions`)
      ]);
      const pos = await posRes.json();
      const act = await actionRes.json();
      return {
        positions: pos.code === 0 ? pos.data : null,
        actions: act.code === 0 ? act.data : null
      };
    } catch (err) {
      console.error(`获取策略 ${sid} 详情失败:`, err);
      return { positions: null, actions: null };
    }
  },

  storage: {
    get(key) {
      try { return JSON.parse(localStorage.getItem('quant_' + key)); } catch { return null; }
    },
    set(key, value) {
      localStorage.setItem('quant_' + key, JSON.stringify(value));
    }
  },

  pollTimer: null,

  startPolling(callback) {
    this.stopPolling();
    const poll = async () => {
      const data = await this.fetchStrategies();
      this.storage.set('lastData', data);
      if (callback) callback(data);
    };
    poll();
    this.pollTimer = setInterval(poll, this.config.pollInterval);
  },

  stopPolling() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
  },

  getCachedData() {
    return this.storage.get('lastData') || this.getMockData();
  }
};

if (typeof module !== 'undefined') module.exports = DataLayer;
