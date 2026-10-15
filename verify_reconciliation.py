#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对账单独立核对：从原始 account_state + daily 逐笔重算，比对 build_reconciliation。"""
import sys, json
from pathlib import Path
sys.path.insert(0, "api"); sys.path.insert(0, ".")
import live_aggregator as la

ROOT = Path("live-data")
DAILY = ROOT / "daily"
STATE = ROOT / "_account_state"
SID_ORDER = ["qixing", "r32", "zhuidian", "sanhe", "lightning", "goldcombo"]

def num(x):
    try: return float(x)
    except: return 0.0

# 1) 对账单（被测函数）
rep = la.build_reconciliation(root=ROOT)
ps = rep["per_strategy"]

# 2) 独立重算
issues = []
def check(name, got, expect, tol=0.02):
    ok = abs(num(got) - num(expect)) <= tol
    if not ok:
        issues.append(f"{name}: 对账单={got} 独立重算={expect}")
    return ok

print("=" * 78)
print(f"{'策略':10s} {'现金':>10} {'市值':>10} {'总资产':>10} {'佣金':>6} {'印花':>6} {'滑点':>6} {'笔数':>4}")
ind_total = {"cash":0,"mv":0,"asset":0,"comm":0,"stamp":0,"slip":0,"cnt":0}
for sid in SID_ORDER:
    if sid not in ps:
        print(f"!! 对账单缺失策略 {sid}"); issues.append(f"缺失策略 {sid}"); continue
    # 2a. 账户账本
    st = json.loads((STATE / f"{sid}.json").read_text())
    cash_state = num(st.get("cash"))
    # 2b. 窗口内所有 daily trades 独立汇总
    comm=stamp=trans=slip=0.0; cnt=0
    latest_rec=None; latest_day=""
    for daydir in sorted(DAILY.iterdir()):
        if not daydir.is_dir(): continue
        f = daydir / f"{sid}.json"
        if not f.exists(): continue
        rec = json.loads(f.read_text())
        latest_rec, latest_day = rec, daydir.name
        for t in rec.get("trades_today", []) or []:
            comm += num(t.get("commission"))
            stamp += num(t.get("stamp_tax"))
            trans += num(t.get("transfer_fee"))
            s = t.get("slippage")
            slip += num(s if s is not None else num(t.get("amount"))*0.001)
            cnt += 1
    # 2c. 最新 daily 快照
    cash_d = num(latest_rec.get("cash"))
    mv = num(latest_rec.get("market_value"))
    asset = num(latest_rec.get("total_asset"))
    # 2d. 独立验证持仓市值：positions 市值之和
    mv_calc = 0.0
    for p in latest_rec.get("positions", []) or []:
        # daily positions 结构：尽量取 qty 和最新价
        qty = num(p.get("qty"))
        px = num(p.get("latest_price", p.get("price", p.get("close_price"))))
        mv_calc += qty * px
    # 输出
    r = ps[sid]
    print(f"{r['name']:10s} {r['cash']:>10.2f} {r['market_value']:>10.2f} {r['total_asset']:>10.2f} "
          f"{r['total_commission']:>6.2f} {r['total_stamp_tax']:>6.2f} {r['total_slippage']:>6.2f} {r['trades_count']:>4d}")
    # 逐项核对
    check(f"{sid}.现金(vs账本)", r["cash"], cash_state)
    check(f"{sid}.现金(vs最新daily)", r["cash"], cash_d)
    check(f"{sid}.市值", r["market_value"], mv)
    check(f"{sid}.总资产=现金+市值", r["total_asset"], r["cash"]+r["market_value"])
    check(f"{sid}.佣金", r["total_commission"], comm)
    check(f"{sid}.印花税", r["total_stamp_tax"], stamp)
    check(f"{sid}.滑点", r["total_slippage"], slip)
    if r["trades_count"] != cnt:
        issues.append(f"{sid}.笔数: 对账单={r['trades_count']} 独立={cnt}")
    # 若能算出市值，核对
    if mv_calc > 0:
        if abs(mv_calc - mv) > 0.05:
            issues.append(f"{sid}.市值 vs 持仓×最新价: 对账单={mv:.2f} 重算={mv_calc:.2f}")
    ind_total["cash"]+=r["cash"]; ind_total["mv"]+=r["market_value"]; ind_total["asset"]+=r["total_asset"]
    ind_total["comm"]+=r["total_commission"]; ind_total["stamp"]+=r["total_stamp_tax"]
    ind_total["slip"]+=r["total_slippage"]; ind_total["cnt"]+=r["trades_count"]

print("-" * 78)
t = rep["totals"]
print(f"汇总: 现金={t['cash']} 市值={t['market_value']} 总权益={t['total_equity']} 成交笔数={rep['orders_total']}")
check("汇总.现金", t["cash"], ind_total["cash"])
check("汇总.市值", t["market_value"], ind_total["mv"])
check("汇总.总权益", t["total_equity"], ind_total["asset"])
if rep["orders_total"] != ind_total["cnt"]:
    issues.append(f"汇总.笔数: 对账单={rep['orders_total']} 独立={ind_total['cnt']}")

print("=" * 78)
print("overall_match:", rep["overall_match"], "| orders_total:", rep["orders_total"])
print("=" * 78)
if issues:
    print(f"发现 {len(issues)} 处不一致：")
    for i in issues: print("  [不一致]", i)
else:
    print("结果：PASS — 对账单全部数据与原始账本/逐笔重算一致。")
