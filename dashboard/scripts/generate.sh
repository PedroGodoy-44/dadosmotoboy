#!/usr/bin/env bash
# generate.sh — atalho para regenerar o HTML do dashboard manualmente.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$BASE"
"$BASE/.venv/bin/python" -m collector.collector --relatorio "$@"
