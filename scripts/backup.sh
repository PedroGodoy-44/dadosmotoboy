#!/usr/bin/env bash
# =============================================================================
#  backup.sh — backup consistente do banco + config + escala.
#  Usa a API de backup do SQLite (nao copia arquivo "quente") para nao correr
#  risco de corrupcao com o coletor escrevendo. NUNCA inclui .env/tokens.
# =============================================================================
set -euo pipefail
BASE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$BASE/backups"
TMP="$(mktemp -d)"
mkdir -p "$OUT_DIR"

DB="$BASE/collector/database.db"
if [[ -f "$DB" ]]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB" ".backup '$TMP/database.db'"
  else
    # fallback: VACUUM INTO via python (snapshot consistente)
    "$BASE/.venv/bin/python" - "$DB" "$TMP/database.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
c = sqlite3.connect(src); c.execute("VACUUM INTO ?", (dst,)); c.close()
PY
  fi
fi
[[ -f "$BASE/collector/config.json" ]] && cp "$BASE/collector/config.json" "$TMP/" || true
[[ -f "$BASE/collector/escala.csv" ]] && cp "$BASE/collector/escala.csv" "$TMP/" || true

TARBALL="$OUT_DIR/motoboys-$STAMP.tar.gz"
tar -czf "$TARBALL" -C "$TMP" .
rm -rf "$TMP"
echo "Backup: $TARBALL"

# mantem os 14 mais recentes
ls -1t "$OUT_DIR"/motoboys-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
