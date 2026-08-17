#!/usr/bin/env python3
import sys
import datetime
import os

def main():
    log_dir = os.path.expanduser('~/.hermes/work_logs/qixing')
    signals_dir = os.path.expanduser('~/quant-monitor-local/signals')
    os.makedirs(signals_dir, exist_ok=True)
    # Find latest log file
    try:
        logs = [f for f in os.listdir(log_dir) if f.endswith('.log') or f.endswith('.txt')]
        if not logs:
            print("No log files to sync")
            return
        latest = max(logs, key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
        src = os.path.join(log_dir, latest)
        dst = os.path.join(signals_dir, latest)
        with open(src, 'r') as f_in, open(dst, 'w') as f_out:
            f_out.write(f_in.read())
        print(f"Synced {latest} to signals")
    except Exception as e:
        print(f"Error syncing: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()