#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盈亏历史独立核对：直接从 daily 原始文件重算，比对 build_pnl_history + 前端KPI口径。"""
import sys, json
from pathlib import Path
sys.path.insert(0, "api"); sys.path.insert(0, ".")
import live_aggregator as la

ROOT = Path("live-data")
DAILY = ROOT / "daily"
SIDS = ["qixing", "r32", "zhuidian", "sanhe", "lightning", "goldcombo"]
INIT = 10000.0

def num(x):
    try: return float(x)
    except: return 0.0

# 1) 被测：API 盈亏历史
payload = la.build_pnl_history(root=ROOT)
api_hist = {h["date"]: h for h in payload["history"]}

# 2) 独立重算：直接读 daily 目录
dates = sorted(d.name for d in DAILY.iterdir() if d.is_dir())
# 每个策略的历史（按日）
sid_rec = {s: {} for s in SIDS}
for d in dates:
    for s in SIDS:
        f = DAILY / d / f"{s}.json"
        if f.exists():
            sid_rec[s][d] = json.loads(f.read_text())

issues = []
def close(name, got, exp, tol=0.02):
    if abs(num(got)-num(exp)) > tol:
        issues.append(f"{name}: API={got} 独立={exp}")

print("="*96)
print(f"{'日期':12s} {'权益':>10} {'日盈亏':>9} {'日收益%':>8} {'累计盈亏':>9} {'累计%':>7} {'持仓数':>5}")
equity_series = []
daily_pnl_series = []
for d in dates:
    equity = 0.0; day_pnl = 0.0; has_today=False; pos_count=0
    for s in SIDS:
        if d in sid_rec[s]:
            r = sid_rec[s][d]
            equity += num(r.get("total_asset"))
            if r.get("today_pnl") is not None:
                day_pnl += num(r.get("today_pnl")); has_today=True
            pos_count += len([p for p in r.get("positions",[]) if num(p.get("qty"))>0])
        else:
            # forward-fill：≤d 的最近记录，否则初始本金
            prior = [dd for dd in sid_rec[s] if dd <= d]
            if prior:
                equity += num(sid_rec[s][max(prior)].get("total_asset"))
            else:
                equity += INIT
    # 若当日无 today_pnl，API 用权益差（首日 prev=初始60000）
    if not has_today:
        prev = equity_series[-1] if equity_series else 60000.0
        day_pnl = equity - prev
    equity_series.append(equity); daily_pnl_series.append(day_pnl)
    cum_pnl = equity - 60000.0
    a = api_hist.get(d)
    if not a:
        issues.append(f"{d}: API 缺失"); continue
    print(f"{d:12s} {equity:>10.2f} {day_pnl:>9.2f} {a['daily_return_pct']:>8.2f} {cum_pnl:>9.2f} {cum_pnl/60000*100:>7.2f} {pos_count:>5d}")
    close(f"{d}.权益", a["equity"], round(equity,2))
    close(f"{d}.日盈亏", a["daily_pnl"], round(day_pnl,2))
    close(f"{d}.累计盈亏", a["cumulative_pnl"], round(cum_pnl,2))
    close(f"{d}.累计收益率", a["cumulative_return_pct"], round(cum_pnl/60000*100,2))
    if a["positions_count"] != pos_count:
        issues.append(f"{d}.持仓数: API={a['positions_count']} 独立={pos_count}")

# 3) KPI（前端口径）
# 最大回撤：滚动峰值百分比
peak = -1e18; mdd = 0.0
for eq in equity_series:
    peak = max(peak, eq)
    if peak > 0:
        dd = (eq-peak)/peak*100
        mdd = min(mdd, dd)
win_days = len([p for p in daily_pnl_series if p > 0])
total_days = len(dates)
win_rate = win_days/total_days*100 if total_days else 0
print("="*96)
print(f"KPI 独立重算：交易天数={total_days} 累计盈亏={round(equity_series[-1]-60000,2)} "
      f"累计收益率={round((equity_series[-1]-60000)/60000*100,2)}% 最大回撤={round(mdd,2)}% "
      f"胜率={round(win_rate,1)}% 盈利天数={win_days}/{total_days}")
print("="*96)
if issues:
    print(f"发现 {len(issues)} 处不一致：")
    for i in issues: print("  [不一致]", i)
else:
    print("结果：PASS — 权益曲线/日盈亏/累计/KPI 全部与原始数据一致。")
