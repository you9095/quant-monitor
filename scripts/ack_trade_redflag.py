#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人工解除成交红灯（红标）
========================
仅当你已经人工核对过账本、确认行情/账目无误后运行。运行后：
  1. 把 live-data/_run_logs/trade_redflag.json 标记为 acknowledged（保留留痕）；
  2. 写一条 redflag_acknowledged 健康心跳并上传 GitHub（Mac 面板随即灭红灯）；
  3. 下一交易窗口起恢复自动成交。

注意（用户铁律）：被红灯冻结的那一天【不补单】，本脚本绝不补任何成交。
全程模拟盘、本机真实撮合，不连接任何券商真实账号/资金账号。

用法：
  python scripts/ack_trade_redflag.py            # 解除并上传
  python scripts/ack_trade_redflag.py --status   # 只查看当前红灯状态
  python scripts/ack_trade_redflag.py --no-push  # 解除但不上传（本地）
"""
import sys
import json
import argparse
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "api"))

import trade_redflag as rf  # noqa: E402

LOG_DIR = BASE / "live-data" / "_run_logs"
HEALTH_FILE = LOG_DIR / "trade_health.json"


def write_health(payload):
    from datetime import datetime
    payload.setdefault("updated_at", datetime.now().isoformat(timespec="seconds"))
    payload["mode"] = "live_simulation_local_match_no_broker"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def push():
    try:
        r = subprocess.run([sys.executable, str(BASE / "scripts" / "sync_live_data.py"), "push"],
                           cwd=str(BASE), capture_output=True, text=True, timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        ok = ("[成功]" in out) or ("[提示]" in out) or r.returncode == 0
        return ok, out.strip()[-200:]
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="只查看红灯状态")
    ap.add_argument("--no-push", action="store_true", help="解除但不上传")
    args = ap.parse_args()

    flag = rf.load_redflag(LOG_DIR)
    if args.status:
        if not flag:
            print("无未解除红灯（红标）。")
            return 0
        print("🚩 存在未解除红灯（红标）：")
        print(json.dumps({k: flag.get(k) for k in
                          ("failed_date", "raised_at", "last_seen_date", "attempt",
                           "pending_strategies", "retry_reasons", "price_sources", "note")},
                         ensure_ascii=False, indent=2))
        return 2

    if not flag:
        print("当前没有未解除红灯，无需操作。")
        return 0

    ok, info = rf.acknowledge(LOG_DIR, note="人工核对后解除（scripts/ack_trade_redflag.py）")
    if not ok:
        print(info)
        return 1
    print(f"✅ 红灯已人工解除（事故日 {info.get('failed_date')}，"
          f"解除于 {info.get('acknowledged_at')}）。")
    print("   被冻结日不补单；下一交易窗口起恢复自动成交。")

    from datetime import date
    write_health({
        "date": date.today().isoformat(), "is_trading_day": None,
        "status": "redflag_acknowledged", "redflag_active": False,
        "failed_date": info.get("failed_date"),
        "attempt": 0, "strategies": {}, "done_count": 0, "total": 6,
        "trades_total": 0, "next_retry_at": None,
        "note": "成交红灯已由人工核对解除；下一交易窗口恢复自动成交，被冻结日不补单。"})

    if args.no_push:
        print("已写入本地（--no-push，未上传）。")
        return 0
    pushed, msg = push()
    print("解除心跳已上传 GitHub。" if pushed else f"解除已写入本地，但上传失败：{msg}\n可稍后重跑本脚本或等下次任务补传。")
    return 0 if pushed else 0


if __name__ == "__main__":
    sys.exit(main())
