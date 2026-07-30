#!/usr/bin/env bash
# update.sh — atualiza codigo + deps e reinicia o coletor.
set -euo pipefail
BASE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$BASE"

if [[ -d "$BASE/.git" ]]; then
  echo "==> git pull..."
  git pull --ff-only || echo "   (git pull falhou/ignorado)"
fi

echo "==> Atualizando dependencias..."
"$BASE/.venv/bin/pip" install --quiet --upgrade -r "$BASE/collector/requirements.txt"

echo "==> Reinstalando units (caso tenham mudado)..."
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
for u in motoboys-collector.service motoboys-report.service motoboys-report.timer \
         motoboys-deploy.path motoboys-deploy.service; do
  sed "s|%BASE%|$BASE|g" "$BASE/systemd/$u" > "$UNIT_DIR/$u"
done
systemctl --user daemon-reload
systemctl --user restart motoboys-collector.service
echo "==> Atualizado e reiniciado."
