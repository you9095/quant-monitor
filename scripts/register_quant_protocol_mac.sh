#!/bin/bash
# ============================================================
# One-time registration of the quant:// protocol handler on macOS.
# After running this once, clicking "Start backend" inside
# index.html launches QuantLauncher.app, which starts the backend.
# Safe to run again (idempotent).
# ============================================================
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/QuantLauncher.app"
LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

if [ ! -d "$APP" ]; then
  echo "[ERROR] QuantLauncher.app not found next to this script: $APP"
  exit 1
fi

chmod +x "$APP/Contents/MacOS/QuantLauncher"
"$LSREG" -R -f "$APP"
echo "[OK] quant:// protocol registered -> $APP"
