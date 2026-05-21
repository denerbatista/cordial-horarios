#!/usr/bin/env bash
# Sync local — sobe o servidor HTTP em 127.0.0.1:8765 e fica esperando
# o site chamar /sync. Pra autostart no WSL/Linux você pode usar systemd
# user service ou rodar via crontab @reboot.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --quiet -r requirements.txt
exec python3 scripts/sync_local.py --server "$@"
