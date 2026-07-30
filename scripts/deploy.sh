#!/usr/bin/env bash
# =============================================================================
#  deploy.sh — publica o dashboard no Cloudflare Pages via Wrangler.
#  Fluxo: relatorio fresco -> wrangler pages deploy -> imprime a URL.
#  Tokens vem do .env (nunca do Git). Aborta com msg clara se faltar algo.
# =============================================================================
set -euo pipefail

BASE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$BASE"

# --- .env ---------------------------------------------------------------------
if [[ -f "$BASE/.env" ]]; then
  set -a; source "$BASE/.env"; set +a
fi
: "${CF_PAGES_PROJECT:=motoboys}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "!! Faltam CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID no .env — deploy abortado." >&2
  echo "   Preencha $BASE/.env e tente de novo." >&2
  exit 1
fi

# --- wrangler disponivel? -----------------------------------------------------
WRANGLER=""
if [[ -x "$BASE/cloudflare/node_modules/.bin/wrangler" ]]; then
  WRANGLER="$BASE/cloudflare/node_modules/.bin/wrangler"
elif command -v wrangler >/dev/null 2>&1; then
  WRANGLER="wrangler"
elif command -v npx >/dev/null 2>&1; then
  WRANGLER="npx --yes wrangler"
else
  echo "!! Node/Wrangler ausentes — deploy abortado." >&2
  echo "   Instale:  sudo pacman -S nodejs npm  &&  (cd cloudflare && npm install)" >&2
  exit 1
fi

# --- relatorio fresco ---------------------------------------------------------
echo "==> Gerando relatorio..."
"$BASE/.venv/bin/python" -m collector.collector --relatorio || true

# --- publica ------------------------------------------------------------------
echo "==> Publicando em Cloudflare Pages (projeto: $CF_PAGES_PROJECT)..."
cd "$BASE/cloudflare"
$WRANGLER pages deploy "$BASE/dashboard/html" \
  --project-name="$CF_PAGES_PROJECT" \
  --commit-dirty=true
