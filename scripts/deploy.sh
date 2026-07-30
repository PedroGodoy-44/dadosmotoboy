#!/usr/bin/env bash
# =============================================================================
#  deploy.sh — publica o dashboard via Git -> Cloudflare Pages.
#  Regenera o HTML; se mudou, commita e da push. O Cloudflare Pages (conectado
#  ao repositorio) publica automaticamente a cada push. Sem Node/wrangler/token.
#  Chamado pelo systemd (motoboys-deploy.path) sempre que o HTML muda.
# =============================================================================
set -euo pipefail

BASE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$BASE"

HTML="dashboard/html/index.html"

# 1) HTML fresco (write-if-changed: so reescreve se o conteudo mudou)
"$BASE/.venv/bin/python" -m collector.collector --relatorio || true

# 2) nada mudou em relacao ao ultimo commit? nao faz nada (evita commit vazio)
if git diff --quiet -- "$HTML" && git ls-files --error-unmatch "$HTML" >/dev/null 2>&1; then
  echo "Dashboard sem alteracao — nada a publicar."
  exit 0
fi

# 3) commit + push -> Cloudflare Pages publica sozinho
git add "$HTML"
git commit -m "dashboard: atualiza $(date '+%Y-%m-%d %H:%M')" \
  || { echo "Nada para commitar."; exit 0; }

if git push; then
  echo "Push enviado — Cloudflare Pages vai publicar em instantes."
else
  echo "!! git push falhou (chave SSH? repo?). O commit local ficou salvo." >&2
  exit 1
fi
