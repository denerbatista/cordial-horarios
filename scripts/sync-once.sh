#!/usr/bin/env bash
# Sync local — roda 1 vez agora (build + commit + push).
# Uso (WSL ou Linux/macOS):
#   scripts/sync-once.sh
# Requer Python 3.11+ e o repo clonado.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --quiet -r requirements.txt
exec python3 scripts/sync_local.py "$@"
