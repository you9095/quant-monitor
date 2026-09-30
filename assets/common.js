/* ============================================================
   common.js — 全站公共 JS 工具函数
   所有子页面(pnl_history/trades/reconciliation)共用
   ============================================================ */

const API_BASE = '';

const STRATEGY_COLORS = {
  zhuidian: '#94a3b8', qixing: '#3b82f6', r32: '#10b981',
  sanhe: '#a855f7', lightning: '#eab308', goldcombo: '#ef4444'
};

const STRATEGY_NAMES = {
  qixing: '七星', r32: '三驾', zhuidian: '追电',
  sanhe: '三合', lightning: '闪电', goldcombo: '黄金A'
};

/** 格式化金额：+1,234.56 / -567.89 */
function formatMoney(v) {
  if (v === null || v === undefined) return '--';
  return (v >= 0 ? '+' : '') + v.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

/** 格式化百分比：+12.34% */
function formatPct(v) {
  if (v === null || v === undefined) return '--';
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
}

/** 格式化价格：1.2345 */
function formatPrice(v) {
  if (v === null || v === undefined) return '--';
  return Number(v).toFixed(4);
}

/** 盈亏 CSS class：正绿负红 */
function pnlClass(v) { return v > 0 ? 'pnl-pos' : (v < 0 ? 'pnl-neg' : ''); }

/** 顶部栏实时时钟 */
function initTopbarClock() {
  const el = document.getElementById('topbar-time');
  if (!el) return;
  function tick() {
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    el.textContent = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  }
  tick();
  setInterval(tick, 1000);
}

/** fetch 封装：自动解析 JSON，错误抛异常 */
async function apiFetch(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// 页面加载后自动初始化时钟
document.addEventListener('DOMContentLoaded', initTopbarClock);
