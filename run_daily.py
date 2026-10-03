#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日实盘入口（转发到 run_daily_engine.py 两段式引擎）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_daily_engine import main

if __name__ == "__main__":
    main()
