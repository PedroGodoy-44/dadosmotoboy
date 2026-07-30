#!/usr/bin/env bash
# start.sh — inicia o coletor + timer de relatorio + watcher de deploy.
set -euo pipefail
systemctl --user start \
  motoboys-collector.service \
  motoboys-report.timer \
  motoboys-deploy.path
echo "Iniciado. Status: ./status.sh"
