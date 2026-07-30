#!/usr/bin/env bash
# stop.sh — para o coletor + timer + watcher (nao desabilita do boot).
set -euo pipefail
systemctl --user stop \
  motoboys-collector.service \
  motoboys-report.timer \
  motoboys-deploy.path 2>/dev/null || true
echo "Parado. (Para desligar do boot: systemctl --user disable ...)"
