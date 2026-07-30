#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collector.py — CLI/entrypoint do coletor de presença de motoboys.

Uso:
  python -m collector.collector --importar-curl curl.txt
  python -m collector.collector --testar
  python -m collector.collector --coletar          # loop (serviço systemd)
  python -m collector.collector --coletar --uma-vez
  python -m collector.collector --relatorio [--dia YYYY-MM-DD]
  python -m collector.collector --mock --relatorio # preview sem painel
  python -m collector.collector --init             # só cria o banco
"""

import argparse
import json
import sys
import time

from . import report as report_mod
from .config import (AMOSTRA_PATH, CONFIG_PATH, DB_PATH, FRESCOR_MIN, INTERVALO,
                     agora, carregar_env, get_logger)
from .curl_import import carregar_config, importar
from .database import db_init, gravar, registrar_coleta
from .panel import classificar, fetch
from .presence import parse_ultimo_acesso

log = get_logger()

# Sem config e sem sessão o coletor NÃO sai (evita crash-loop sob Restart=always):
# espera este intervalo e re-verifica se o config.json apareceu.
ESPERA_SEM_CONFIG = 60


def cmd_importar(arquivo, intervalo, frescor):
    cfg = importar(arquivo, intervalo, frescor)
    print(f"OK -> {CONFIG_PATH}\n  {cfg['metodo']} {cfg['url']}")
    print(f"  {len(cfg['headers'])} headers" + (" + body" if cfg["body"] else ""))
    print("\nProximo: python -m collector.collector --testar")


def cmd_testar(cfg):
    http, data, erro = fetch(cfg)
    if erro == "SESSAO_EXPIRADA":
        sys.exit("Sessao do painel expirou. Recapture o cURL e rode --importar-curl.")
    if erro:
        sys.exit(f"Falhou: {erro}")

    with open(AMOSTRA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    regs, entregas = classificar(data)
    if not regs:
        sys.exit("Nenhum registro com dsStatus. Veja _amostra_mapa.json — "
                 "pode ser a lista de estabelecimentos ou de clientes.")

    ts = agora()
    print(f"\nHTTP {http} — {len(regs)} entregadores, "
          f"{len(entregas)} entregas em curso\n")
    print(f"{'NOME':<30}{'ULT.ACESSO':>12}{'DEFASAGEM':>11}{'PED':>5}  ESTADO")
    print("-" * 74)
    pres = 0
    for r in sorted(regs, key=lambda x: str(x.get("dsNome") or "")):
        ua = parse_ultimo_acesso(r.get("dsStatus"), ts)
        d = (ts - ua).total_seconds() / 60 if ua else None
        ok = d is not None and d <= FRESCOR_MIN
        pres += ok
        qt = int(r.get("qtPedidos") or 0)
        est = "AUSENTE" if not ok else ("RODANDO" if qt > 0 else "ONLINE")
        print(f"{str(r.get('dsNome'))[:29]:<30}"
              f"{(ua.strftime('%H:%M:%S') if ua else '?'):>12}"
              f"{('?' if d is None else f'{d:.0f} min'):>11}{qt:>5}  {est}")

    print(f"\n{pres} presentes / {len(regs)} cadastrados "
          f"(limite de frescor: {FRESCOR_MIN} min)")
    print("\nOK. Proximo: python -m collector.collector --coletar")


def cmd_coletar(uma_vez=False):
    """Loop de coleta resiliente: recarrega o config a cada ciclo, nunca sai
    sozinho por falta de sessão (deixa o systemd manter vivo)."""
    con = db_init()
    log.info(f"coletor iniciado — db={DB_PATH}")
    while True:
        cfg = carregar_config()
        if cfg is None:
            log.warning("sem config.json — rode --importar-curl. "
                        f"Reverificando em {ESPERA_SEM_CONFIG}s.")
            if uma_vez:
                return
            time.sleep(ESPERA_SEM_CONFIG)
            continue

        iv = int(cfg.get("intervalo_seg") or INTERVALO)
        ts = agora().replace(microsecond=0)
        http, data, erro = fetch(cfg)
        if erro:
            registrar_coleta(con, ts, http, None, None, erro)
            log.warning(f"!! {erro}"
                        + (" — recapture o cURL (--importar-curl)"
                           if erro == "SESSAO_EXPIRADA" else ""))
        else:
            regs, entregas = classificar(data)
            n = gravar(con, ts, regs, int(cfg.get("frescor_min") or FRESCOR_MIN),
                       entregas=entregas)
            registrar_coleta(con, ts, http, len(regs), n, None)
            log.info(f"{n} presentes de {len(regs)} cadastrados")

        if uma_vez:
            return
        time.sleep(iv)


def cmd_relatorio(dia=None):
    if not DB_PATH.exists():
        sys.exit(f"{DB_PATH} nao existe. Rode --coletar (ou --mock).")
    con = db_init()
    pay, path, mudou = report_mod.gerar(con, dia)
    if pay is None:
        sys.exit("Sem snapshots.")
    print(f"HTML: {path}" + ("" if mudou else "  (sem alteracao)"))


def main():
    carregar_env()
    ap = argparse.ArgumentParser(description="Presenca real de motoboys")
    ap.add_argument("--importar-curl", metavar="ARQ")
    ap.add_argument("--testar", action="store_true")
    ap.add_argument("--coletar", action="store_true")
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument("--relatorio", action="store_true")
    ap.add_argument("--dia")
    ap.add_argument("--intervalo", type=int, default=INTERVALO)
    ap.add_argument("--frescor", type=int, default=FRESCOR_MIN)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--init", action="store_true")
    a = ap.parse_args()

    if a.init:
        db_init()
        return print(f"banco inicializado: {DB_PATH}")

    if a.importar_curl:
        return cmd_importar(a.importar_curl, a.intervalo, a.frescor)

    if a.mock:
        from .mock import gerar_mock
        gerar_mock()
        a.relatorio = True

    if a.testar:
        cfg = carregar_config()
        if cfg is None:
            sys.exit("Sem config.json. Rode --importar-curl primeiro.")
        return cmd_testar(cfg)

    if a.coletar:
        return cmd_coletar(a.uma_vez)

    if a.relatorio:
        return cmd_relatorio(a.dia)

    ap.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrompido.")
