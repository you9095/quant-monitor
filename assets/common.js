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

/* ============================================================
   数据模式：模拟盘(simulator) / 实盘模拟(live)
   约定：localStorage.data_mode ∈ simulator|live，与首页 index.html 共用。
   - 模拟盘：信号回测，不真实成交、不记现金/持仓/账单。
   - 实盘模拟：Windows 本机按真实行情撮合、真实记账，非回测，不接任何券商。
   ============================================================ */
function getDataMode() {
  // 支持 URL ?data_mode=live|simulator 临时指定（便于截图/分享直链）
  try {
    const q = new URLSearchParams(location.search).get('data_mode');
    if (q === 'live' || q === 'simulator') return q;
  } catch (e) { /* ignore */ }
  return localStorage.getItem('data_mode') === 'live' ? 'live' : 'simulator';
}
function setDataMode(m) { localStorage.setItem('data_mode', m); }
/** 给请求 URLSearchParams 附带 data_mode，返回同一对象便于链式调用 */
function withMode(params) {
  params = params || new URLSearchParams();
  params.set('data_mode', getDataMode());
  return params;
}
const MODE_HINT = {
  simulator: '模拟盘：仅产出买卖信号与回测收益，不真实成交，不产生现金 / 持仓 / 账单。',
  live: '实盘模拟：Windows 本机按真实行情真实撮合、真实记账，非回测，不连接任何券商真实账号。'
};

/** 顶部「模拟/实盘」切换按钮（自动注入到每个 .topbar） */
function mountModeToggle() {
  document.querySelectorAll('.topbar').forEach(bar => {
    if (bar.querySelector('.data-mode-toggle')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'data-mode-toggle';
    btn.addEventListener('click', () => {
      setDataMode(getDataMode() === 'live' ? 'simulator' : 'live');
      location.href = location.pathname;   // 去掉 ?data_mode=，按本地存储模式干净跳转
    });
    bar.appendChild(btn);
  });
  updateModeToggle();
}
function updateModeToggle() {
  const live = getDataMode() === 'live';
  document.querySelectorAll('.data-mode-toggle').forEach(b => {
    b.textContent = live ? '● 实盘模拟 · 点击切回模拟盘' : '○ 模拟盘 · 点击切换实盘模拟';
    b.classList.toggle('live', live);
  });
}

/** 数据性质横幅（自动插到 main 前）；fetch 返回后用 updateNatureBanner(payload) 精确更新 */
function mountNatureBanner() {
  if (document.getElementById('data-nature-banner')) return;
  const main = document.querySelector('main.container') || document.querySelector('main');
  const div = document.createElement('div');
  div.id = 'data-nature-banner';
  div.className = 'data-nature-banner';
  if (main && main.parentNode) main.parentNode.insertBefore(div, main);
  else document.body.prepend(div);
  updateNatureBanner(null);
}
function updateNatureBanner(payload) {
  const el = document.getElementById('data-nature-banner');
  if (!el) return;
  const mode = getDataMode();
  let cls, text;
  if (payload && payload.is_ui_mock) {
    cls = 'mock';
    text = (payload.data_nature_label || '') + '　⚠️ 以下数字均为虚拟，非实盘 / 非回测';
  } else if (mode === 'live') {
    cls = 'live';
    text = (payload && payload.data_nature_label) ||
           '实盘模拟（Windows 本机真实撮合，非回测，不接任何券商）';
  } else {
    cls = 'sim';
    text = (payload && payload.data_nature_label) || '模拟盘（信号回测，非真实成交）';
  }
  const note = payload && payload.note
    ? `<div class="banner-note">${payload.note}</div>` : '';
  el.className = 'data-nature-banner ' + cls;
  el.innerHTML = `<div class="banner-main">${text}</div>${note}`;
}

// ============================================================
// 全站表格统一分页：每页 10 行；列数 >10 的宽表横向滚动、列全保留
// 自动接管动态渲染（fetch 后 innerHTML 注入 / Tab 切换重建）的表格
// ============================================================
const PG_PAGE_SIZE = 10;

// 支持 URL #page=n 直链定位初始页（便于分享/核验）；筛选或重渲染后仍回到第 1 页
function pgInitialPage() {
  const m = /page=(\d+)/.exec(location.hash || '');
  const n = m ? parseInt(m[1], 10) : 1;
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

function pgColCount(table) {
  if (table.tHead && table.tHead.rows[0]) return table.tHead.rows[0].cells.length;
  const tb = table.tBodies[0];
  return tb && tb.rows[0] ? tb.rows[0].cells.length : 0;
}

function pgIsEmptyPlaceholder(table, rows) {
  // 单行且单元格带 colspan（如“暂无数据”），视为空态，不分页
  return rows.length === 1 && rows[0].querySelector('[colspan]');
}

function pgRenderPager(table, total, pages, cur) {
  const p = table._pgPager;
  p.style.display = 'flex';
  p.innerHTML = '';
  const info = document.createElement('span');
  info.className = 'pg-info';
  info.textContent = `共 ${total} 条 · 第 ${cur}/${pages} 页`;
  p.appendChild(info);

  const mk = (label, page, opts) => {
    opts = opts || {};
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'pg-btn' + (opts.active ? ' active' : '');
    b.textContent = label;
    b.title = opts.title || '';
    b.disabled = !!opts.disabled;
    if (!opts.disabled) {
      b.addEventListener('click', () => { table._pgPage = page; pgRefresh(table); });
    }
    return b;
  };

  p.appendChild(mk('«', 1, { disabled: cur === 1, title: '首页' }));
  p.appendChild(mk('‹', cur - 1, { disabled: cur === 1, title: '上一页' }));
  let st = Math.max(1, cur - 2);
  let en = Math.min(pages, st + 4);
  st = Math.max(1, en - 4);
  for (let i = st; i <= en; i++) p.appendChild(mk(String(i), i, { active: i === cur }));
  p.appendChild(mk('›', cur + 1, { disabled: cur === pages, title: '下一页' }));
  p.appendChild(mk('»', pages, { disabled: cur === pages, title: '末页' }));
}

function pgRefresh(table) {
  const tb = table.tBodies[0];
  if (!tb || !table._pgPager) return;
  const rows = Array.from(tb.rows);
  const total = rows.length;
  if (pgIsEmptyPlaceholder(table, rows) || total <= PG_PAGE_SIZE) {
    rows.forEach(r => { r.style.display = ''; });
    table._pgPager.style.display = 'none';
    return;
  }
  const pages = Math.ceil(total / PG_PAGE_SIZE);
  let cur = Math.min(Math.max(1, table._pgPage || 1), pages);
  table._pgPage = cur;
  const s = (cur - 1) * PG_PAGE_SIZE;
  rows.forEach((r, i) => { r.style.display = (i >= s && i < s + PG_PAGE_SIZE) ? '' : 'none'; });
  pgRenderPager(table, total, pages, cur);
}

function pgAttach(table) {
  if (table.dataset.pg === '1') return;
  const tb = table.tBodies[0];
  if (!tb) return;
  table.dataset.pg = '1';
  table._pgPage = pgInitialPage();
  table._pgEverData = tb.rows.length > 0 && !pgIsEmptyPlaceholder(table, Array.from(tb.rows));

  // 宽表：保证横向滚动且列不被压缩
  let host = null;
  if (pgColCount(table) > 10) {
    table.classList.add('paged-wide');
    const parent = table.parentElement;
    if (parent && parent.classList.contains('table-wrapper')) {
      parent.classList.add('paged-scroll');
      host = parent;
    } else if (parent) {
      const w = document.createElement('div');
      w.className = 'table-wrapper paged-scroll';
      parent.insertBefore(w, table);
      w.appendChild(table);
      host = w;
    }
  }

  const pager = document.createElement('div');
  pager.className = 'table-pager';
  pager.style.display = 'none';
  (host || table).insertAdjacentElement('afterend', pager);
  table._pgPager = pager;

  // 首次数据到达：尊重 URL #page=n；之后筛选/重渲染：回到第 1 页。翻页只改 display，不触发 childList
  new MutationObserver(() => {
    const hasData = tb.rows.length > 0 && !pgIsEmptyPlaceholder(table, Array.from(tb.rows));
    if (!table._pgEverData) { table._pgEverData = hasData; table._pgPage = pgInitialPage(); }
    else { table._pgPage = 1; }
    pgRefresh(table);
  }).observe(tb, { childList: true });

  pgRefresh(table);
}

function pgScan() {
  document.querySelectorAll('table').forEach(pgAttach);
}

function startTablePagination() {
  pgScan();
  let timer = null;
  new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(pgScan, 80);
  }).observe(document.body, { childList: true, subtree: true });
}

// 页面加载后自动初始化：时钟 + 模式切换 + 数据性质横幅 + 表格分页
document.addEventListener('DOMContentLoaded', () => {
  initTopbarClock();
  mountModeToggle();
  mountNatureBanner();
  startTablePagination();
});
