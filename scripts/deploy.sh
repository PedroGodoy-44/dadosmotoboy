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
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

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

# O HTML muda a cada ciclo (o payload carrega "gerado_em"), entao o push e
# frequente. Se o origin andou (outra maquina publicando no mesmo branch), o
# push e recusado — e sem tratamento o commit fica preso divergindo, fazendo
# TODO deploy seguinte falhar para sempre.
if git push; then
  echo "Push enviado — Cloudflare Pages vai publicar em instantes."
  exit 0
fi

# Caminho gentil: nosso commit por cima do que veio do origin.
echo "Push recusado — o origin andou. Tentando rebase ..." >&2
if git pull --rebase && git push; then
  echo "Push enviado apos rebase — o origin tinha andado."
  exit 0
fi
# Um rebase que conflitou deixa o repo pela metade; sem abortar, todo deploy
# seguinte falha com "rebase in progress".
git rebase --abort 2>/dev/null || true

# Chegou aqui: as duas maquinas reescreveram o MESMO index.html e o rebase
# conflitou. Nao ha merge a fazer — o HTML e artefato gerado, sai inteiro do
# banco a cada ciclo, entao a versao recem-gerada simplesmente vence.
# Reconstroi o commit em cima do origin em vez de tentar reconciliar.
git fetch -q origin || { echo "!! fetch falhou (rede?)." >&2; exit 1; }

# Salvaguarda antes do reset --hard: so da para descartar o historico local se
# ele for exclusivamente do HTML. Commit de codigo ou alteracao nao commitada em
# outro arquivo e trabalho humano — para e chama gente. (Arquivo nao rastreado
# nao entra na conta: o reset nao apaga, e travar por causa de um curl.txt
# esquecido no diretorio deixaria o deploy morto sem motivo.)
extras="$(git diff --name-only "origin/$BRANCH...HEAD" -- . ":(exclude)$HTML")"
sujos="$(git status --porcelain -uno -- . ":(exclude)$HTML")"
if [[ -n "$extras$sujos" ]]; then
  echo "!! Dashboard conflitou com o origin E ha trabalho local fora do HTML:" >&2
  printf '%s\n' $extras $sujos | sed 's/^/     /' >&2
  echo "   Resolva a mao (git pull --rebase) — nada foi descartado." >&2
  exit 1
fi

gerado="$(mktemp)"; cp "$HTML" "$gerado"
git reset -q --hard "origin/$BRANCH"
cp "$gerado" "$HTML"; rm -f "$gerado"

if git diff --quiet -- "$HTML"; then
  echo "Dashboard do origin ja era identico — nada a publicar."
  exit 0
fi
git add "$HTML"
git commit -qm "dashboard: atualiza $(date '+%Y-%m-%d %H:%M')"
if git push; then
  echo "Push enviado — dashboard reconstruido sobre o origin."
else
  # O origin andou de novo no meio do caminho. O repo ficou limpo (um unico
  # commit de HTML sobre o origin), entao o proximo ciclo se resolve sozinho.
  echo "!! push falhou de novo; o proximo ciclo tenta do zero." >&2
  exit 1
fi
