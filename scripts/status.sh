#!/usr/bin/env bash
# status.sh — visao geral do coletor, timer e watcher de deploy.
set -euo pipefail
echo "=== coletor ==="
systemctl --user --no-pager status motoboys-collector.service | head -8 || true
echo
echo "=== timers ==="
systemctl --user list-timers --no-pager | grep -E 'motoboys|NEXT' || true
echo
echo "=== watcher de deploy ==="
systemctl --user --no-pager status motoboys-deploy.path | head -5 || true
echo
echo "Logs ao vivo:  journalctl --user -u motoboys-collector -f"
