#!/usr/bin/env python3
"""
aplicar-sessao.py — troca o PHPSESSID dentro de collector/config.json.

Roda NO SERVIDOR, chamado por scripts/renovar-sessao.sh. Recebe o cookie novo
pelo STDIN de proposito: como argumento ele apareceria em `ps` e no histórico do
shell.

Grava com troca atomica (os.replace) para o coletor nunca ler um arquivo pela
metade no meio de um ciclo. O backup vai para FORA do repositorio: o .gitignore
casa `collector/config.json` exato, entao um `config.json.bak` ficaria visivel ao
git — com a sessao viva dentro, num repo que da push sozinho.

Sai com codigo 9 quando o cookie recebido e igual ao que ja estava, para o script
chamador poder pular o restart a toa.
"""
import json
import os
import pathlib
import re
import sys
import time

DESTINO_BACKUP = pathlib.Path.home() / ".local/state/motoboys"


def main() -> None:
    novo = sys.stdin.read().strip()
    if not novo:
        sys.exit("nenhum cookie recebido no stdin")

    alvo = pathlib.Path("collector/config.json")
    if not alvo.exists():
        sys.exit("collector/config.json nao existe — rode --importar-curl uma vez antes")

    cfg = json.loads(alvo.read_text())
    chave = next((k for k in cfg["headers"] if k.lower() == "cookie"), None)
    if not chave:
        sys.exit("config.json nao tem header Cookie")

    antes = cfg["headers"][chave]
    depois, trocas = re.subn(r"(PHPSESSID=)[^;]*", lambda m: m.group(1) + novo, antes)
    if not trocas:
        sys.exit("PHPSESSID nao encontrado no header Cookie")

    if antes == depois:
        print("cookie identico ao que ja estava — nada a fazer")
        raise SystemExit(9)

    DESTINO_BACKUP.mkdir(parents=True, exist_ok=True)
    backup = DESTINO_BACKUP / f"config.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    backup.write_text(alvo.read_text())
    backup.chmod(0o600)

    cfg["headers"][chave] = depois
    tmp = alvo.with_name("config.json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    os.replace(tmp, alvo)

    print(f"config.json atualizado (backup em {backup})")


if __name__ == "__main__":
    main()
