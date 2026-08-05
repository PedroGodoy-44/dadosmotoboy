#!/usr/bin/env bash
# =============================================================================
#  install.sh — instala o projeto Motoboys inteiro num comando.
#  venv + deps + banco + units systemd (user) + linger + enable/start.
#  NUNCA usa sudo. Nao precisa de Node: o deploy e via git push.
# =============================================================================
set -euo pipefail

BASE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNITS=(motoboys-collector.service motoboys-report.service motoboys-report.timer
       motoboys-deploy.path motoboys-deploy.service)

echo "==> Projeto: $BASE"

# 1) venv + dependencias -------------------------------------------------------
if [[ ! -d "$BASE/.venv" ]]; then
  echo "==> Criando venv..."
  python3 -m venv "$BASE/.venv"
fi
echo "==> Instalando dependencias..."
"$BASE/.venv/bin/pip" install --quiet --upgrade pip
"$BASE/.venv/bin/pip" install --quiet -r "$BASE/collector/requirements.txt"

# 2) banco SQLite --------------------------------------------------------------
echo "==> Inicializando banco..."
( cd "$BASE" && "$BASE/.venv/bin/python" -m collector.collector --init )

# 3) .env ----------------------------------------------------------------------
if [[ ! -f "$BASE/.env" && -f "$BASE/.env.example" ]]; then
  cp "$BASE/.env.example" "$BASE/.env"
  echo "==> .env criado a partir do exemplo — preencha o HEALTHCHECK_URL."
fi

# 4) systemd (user) ------------------------------------------------------------
echo "==> Instalando units systemd em $UNIT_DIR"
mkdir -p "$UNIT_DIR"
for u in "${UNITS[@]}"; do
  sed "s|%BASE%|$BASE|g" "$BASE/systemd/$u" > "$UNIT_DIR/$u"
done
systemctl --user daemon-reload

echo "==> Habilitando linger (sobrevive a logout/reboot)..."
loginctl enable-linger "$USER" >/dev/null 2>&1 || \
  echo "   (nao consegui habilitar linger automaticamente; rode: loginctl enable-linger $USER)"

echo "==> Habilitando e iniciando servicos..."
systemctl --user enable --now \
  motoboys-collector.service \
  motoboys-report.timer \
  motoboys-deploy.path

echo
echo "==> Pronto. Status:"
systemctl --user --no-pager status motoboys-collector.service | head -6 || true
echo
echo "   Timers:   systemctl --user list-timers | grep motoboys"
echo "   Logs:     journalctl --user -u motoboys-collector -f"
echo
echo "   Falta:  1) sessao do painel -> ./ (venv) -m collector.collector --importar-curl curl.txt"
echo "           2) HEALTHCHECK_URL no .env (alerta de coleta parada)"
