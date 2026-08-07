#!/usr/bin/env bash
# =============================================================================
#  renovar-sessao.sh — renova a sessao do painel no servidor SEM capturar cURL.
#  Roda na MAQUINA LOCAL: le o PHPSESSID do Firefox (onde voce ja esta logado),
#  manda para o servidor, testa e reinicia o coletor.
#
#  Diferenca para push-sessao.sh: aquele parte de um curl.txt capturado no F12;
#  este dispensa a captura. Use aquele quando trocar de maquina ou quando os
#  outros parametros da requisicao mudarem, e este no dia a dia.
#
#  O cookie so trafega por PIPE (stdin do ssh) — nunca vira argumento nem toca
#  o disco do servidor fora do config.json.
#
#  uso: ./scripts/renovar-sessao.sh [ubuntu@IP]
#  O host sai de $MOTOBOYS_HOST quando o argumento e omitido.
# =============================================================================
set -euo pipefail

HOST="${1:-${MOTOBOYS_HOST:-}}"
REMOTO="~/projetos/motoboys"
AQUI="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

if [[ -z "$HOST" ]]; then
  echo "uso: $0 [ubuntu@IP]" >&2
  echo "     (sem argumento, usa \$MOTOBOYS_HOST — ponha no ~/.bashrc:" >&2
  echo "      export MOTOBOYS_HOST=ubuntu@SEU_IP)" >&2
  exit 1
fi

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)

# O aplicador vai embutido em base64 no comando: assim nao precisa de scp e nao
# deixa arquivo para tras. Ele nao contem segredo — o cookie vai pelo stdin.
APLICADOR="$(base64 -w0 < "$AQUI/aplicar-sessao.py")"

echo "==> Lendo a sessao do Firefox ..."
COOKIE_OK=0
set +e
python3 "$AQUI/ler-cookie-firefox.py" | ssh "${SSH_OPTS[@]}" "$HOST" \
  "cd $REMOTO && printf %s '$APLICADOR' | base64 -d > /tmp/aplicar-sessao.py && \
   .venv/bin/python /tmp/aplicar-sessao.py; rc=\$?; rm -f /tmp/aplicar-sessao.py; exit \$rc"
RC=$?
set -e

case "$RC" in
  0) COOKIE_OK=1 ;;
  9) echo "==> A sessao do servidor ja era esta. Seguindo para o teste." ;;
  *) echo "!! Falhou ao aplicar a sessao (codigo $RC)." >&2; exit "$RC" ;;
esac

echo "==> Testando contra o painel ..."
# --testar tambem sai com erro quando simplesmente NAO HA ninguem online (de
# madrugada o painel devolve lista vazia). Isso nao e problema de sessao, entao o
# veredito vem da mensagem, nao do codigo de saida.
set +e
SAIDA="$(ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTO && .venv/bin/python -m collector.collector --testar" 2>&1)"
TESTE_RC=$?
set -e
echo "$SAIDA"

if grep -qi "sessao do painel expirou" <<<"$SAIDA"; then
  echo >&2
  echo "!! O painel recusou a sessao — ela morreu tambem no seu navegador." >&2
  echo "   Abra o painel, faca login de verdade (o captcha e humano por design)" >&2
  echo "   e rode este comando de novo." >&2
  exit 1
fi

if [[ "$TESTE_RC" != "0" ]]; then
  echo
  echo "==> A sessao foi ACEITA, mas o painel nao devolveu ninguem agora."
  echo "    Normal fora do horario de operacao. Confirme de manha com 'make logs'."
fi

if [[ "$COOKIE_OK" == "1" ]]; then
  echo "==> Reiniciando o coletor para pegar a sessao na hora ..."
  ssh "${SSH_OPTS[@]}" "$HOST" "systemctl --user restart motoboys-collector"
fi

echo
echo "==> Sessao renovada. Confira com: make logs   (ou 'journalctl --user -u motoboys-collector -f' no servidor)"
