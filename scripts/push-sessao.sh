#!/usr/bin/env bash
# =============================================================================
#  push-sessao.sh — renova a sessao do painel no servidor remoto.
#  Roda na MAQUINA LOCAL: manda o cURL recem-capturado para o servidor, importa
#  e testa por la. Substitui o ciclo manual scp + make import + make test.
#
#  uso: ./scripts/push-sessao.sh curl.txt [ubuntu@IP]
#  O host sai de $MOTOBOYS_HOST quando o 2o argumento e omitido.
# =============================================================================
set -euo pipefail

CURL_FILE="${1:-}"
HOST="${2:-${MOTOBOYS_HOST:-}}"
REMOTO="~/projetos/motoboys"

if [[ -z "$CURL_FILE" || -z "$HOST" ]]; then
  echo "uso: $0 curl.txt [ubuntu@IP]" >&2
  echo "     (sem o 2o argumento, usa \$MOTOBOYS_HOST)" >&2
  exit 1
fi

if [[ ! -f "$CURL_FILE" ]]; then
  echo "!! arquivo nao encontrado: $CURL_FILE" >&2
  exit 1
fi

# Servidor fora do ar nao pode virar espera infinita — nem na limpeza.
SSH_OPTS=(-o ConnectTimeout=10)

# O cURL carrega o cookie de sessao — some com ele do /tmp remoto em qualquer saida.
limpar() { ssh -o ConnectTimeout=5 "$HOST" "rm -f /tmp/curl.txt" >/dev/null 2>&1 || true; }
trap limpar EXIT

echo "==> Enviando $CURL_FILE para $HOST ..."
scp -q "${SSH_OPTS[@]}" "$CURL_FILE" "$HOST:/tmp/curl.txt"

echo "==> Importando e testando no servidor ..."
ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTO && \
  .venv/bin/python -m collector.collector --importar-curl /tmp/curl.txt && \
  .venv/bin/python -m collector.collector --testar"

echo
echo "==> Sessao renovada. O coletor volta a gravar no proximo ciclo."
