#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成交红灯（红标）跨日锁定
========================
当某交易日 17:00 窗口结束、行情三源（东财→腾讯→新浪）持续重试仍无法取得真实价
成交时，成交监督器会写下一个【持久红标】trade_redflag.json。

用户铁律（2026-10-08 明确）：
  * 17:00 后仍极端失败 → 亮红灯，且红灯【一直亮着，第二天、周末、节假日也继续亮】；
  * 【绝不允许自动跨日补单】（不用昨日收盘价、不在次日补事故日的成交），
    避免疲劳状态/隔日资金口径错误污染账本；
  * 红标未解除前，监督器不再自动成交（含当日正常成交也一并冻结，等人工处理）；
  * 只有人工核对账目后运行 scripts/ack_trade_redflag.py 才解除，解除后从下一交易
    窗口恢复自动成交，被冻结那一天的单据【不补】。

本模块为监督器 / 引擎 / 聚合层 / 解除脚本共用，避免判定逻辑散落多处。
全程模拟盘、本机真实撮合，不连接任何券商真实账号/资金账号。
"""
import json
import socket
from pathlib import Path
from datetime import datetime

DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "live-data" / "_run_logs"
REDFLAG_NAME = "trade_redflag.json"

DEFAULT_NOTE = (
    "17:00 成交窗口结束仍未取得三源真实价：红灯跨日持续，已冻结一切自动成交与补单，"
    "红灯将一直亮到人工核对并解除（scripts/ack_trade_redflag.py），被冻结日不补单。"
)


def redflag_path(log_dir=None) -> Path:
    return Path(log_dir or DEFAULT_LOG_DIR) / REDFLAG_NAME


def _read_raw(log_dir=None):
    p = redflag_path(log_dir)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def load_redflag(log_dir=None):
    """返回【未解除】的红标 dict；无红标或已解除返回 None。"""
    d = _read_raw(log_dir)
    if d and not d.get("acknowledged"):
        return d
    return None


def is_active(log_dir=None) -> bool:
    return load_redflag(log_dir) is not None


def raise_redflag(*, failed_date, strategies=None, pending_strategies=None,
                  retry_reasons=None, price_sources=None, attempt=None,
                  note=None, log_dir=None):
    """写下持久红标。若已有未解除红标，保留首次事故信息，仅刷新最近出现日期。"""
    p = redflag_path(log_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    existing = load_redflag(log_dir)
    if existing:
        existing["last_seen_date"] = failed_date
        existing["updated_at"] = now
        # 持续失败时刷新待成交清单与价源命中，便于人工排查
        if pending_strategies is not None:
            existing["pending_strategies"] = pending_strategies
        if retry_reasons is not None:
            existing["retry_reasons"] = retry_reasons
        if price_sources is not None:
            existing["price_sources"] = price_sources
        flag = existing
    else:
        flag = {
            "status": "pending_overnight",
            "acknowledged": False,
            "failed_date": failed_date,
            "raised_at": now,
            "attempt": attempt,
            "price_sources": price_sources or {},
            "pending_strategies": pending_strategies or [],
            "retry_reasons": retry_reasons or {},
            "strategies": strategies or {},
            "host": socket.gethostname(),
            "note": note or DEFAULT_NOTE,
        }
    p.write_text(json.dumps(flag, ensure_ascii=False, indent=2), encoding="utf-8")
    return flag


def acknowledge(log_dir=None, note=None):
    """人工解除红标（保留文件留痕，置 acknowledged=True）。返回 (ok, info)。"""
    p = redflag_path(log_dir)
    d = _read_raw(log_dir)
    if not d:
        return False, "未找到红标文件，无需解除。"
    if d.get("acknowledged"):
        return False, "红标此前已解除。"
    d["acknowledged"] = True
    d["acknowledged_at"] = datetime.now().isoformat(timespec="seconds")
    d["ack_host"] = socket.gethostname()
    if note:
        d["ack_note"] = note
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, d
