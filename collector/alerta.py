#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alerta.py — sinal de vida do coletor (dead man's switch).

Cobre os DOIS modos de falha, que são diferentes:

  A) Coletando mas falhando — o processo está vivo e o painel devolve erro em
     todo ciclo. Detectado aqui: após ALERTA_FALHAS ciclos seguidos com erro,
     manda um ping /fail.

  B) Não está coletando — processo morto, VM reclamada, rede caída. Código
     nenhum dentro do coletor detecta isso (código morto não alerta). Quem
     detecta é o serviço externo: os pings simplesmente PARAM de chegar e ele
     avisa depois do período + grace configurados no painel dele.

Por isso o ping de sucesso é mandado a CADA ciclo, e não só quando muda de
estado: a ausência dele é que carrega a informação do modo B.

Configuração (.env, ver .env.example):
  HEALTHCHECK_URL   URL do check (ex.: https://hc-ping.com/<uuid>). Vazio = desligado.
  ALERTA_FALHAS     ciclos seguidos com erro antes de sinalizar falha (padrão 5).

REGRA INEGOCIÁVEL: alerta nunca derruba coleta. Toda falha de rede daqui é
engolida e logada — perder um ping é irrelevante perto de perder um snapshot.
"""

import os

try:
    import requests
except ImportError:                                 # pragma: no cover
    requests = None

from .config import get_logger

log = get_logger()

TIMEOUT = 10                    # curto: o ciclo de coleta não pode ficar preso
PADRAO_FALHAS = 5               # 5 ciclos de 3 min = ~15 min antes de gritar

_avisado_desligado = False      # loga "desativado" uma vez só, não a cada ciclo


def _url():
    return (os.environ.get("HEALTHCHECK_URL") or "").strip()


def limiar():
    """Ciclos seguidos com erro antes de sinalizar falha."""
    try:
        return max(1, int(os.environ.get("ALERTA_FALHAS") or PADRAO_FALHAS))
    except ValueError:
        return PADRAO_FALHAS


def ativo():
    global _avisado_desligado
    if _url() and requests is not None:
        return True
    if not _avisado_desligado:
        _avisado_desligado = True
        log.info("alerta desativado (HEALTHCHECK_URL vazio no .env) — "
                 "uma queda prolongada passará despercebida")
    return False


def _ping(sufixo="", corpo=""):
    """Dispara o ping. Nunca levanta exceção, nunca bloqueia por muito tempo."""
    if not ativo():
        return False
    try:
        requests.post(_url().rstrip("/") + sufixo,
                      data=corpo.encode("utf-8")[:9000], timeout=TIMEOUT)
        return True
    except Exception as e:
        # Rede instável aqui não diz nada sobre a saúde da coleta: se o painel
        # respondeu, a coleta está boa mesmo sem o ping sair.
        log.warning(f"ping de alerta falhou ({type(e).__name__}) — coleta segue normal")
        return False


def ok(resumo=""):
    """Sinal de vida do ciclo bem-sucedido. É a AUSÊNCIA disto que detecta o modo B."""
    return _ping("", resumo)


def falha(erro, seguidas):
    """Sinaliza o modo A. Só grita depois de `limiar()` ciclos seguidos com erro.

    Continua pingando /fail enquanto durar: o healthchecks deduplica e não
    manda e-mail repetido, mas assim o estado lá reflete a realidade e o
    horário do último erro fica correto.
    """
    if seguidas < limiar():
        return False
    return _ping("/fail", f"{seguidas} ciclos seguidos com erro: {erro}")


def recuperado(seguidas, resumo=""):
    """Coleta voltou depois de ter gritado. Volta o check para OK."""
    log.info(f"coleta normalizada apos {seguidas} ciclos com erro")
    return _ping("", f"recuperado apos {seguidas} ciclos com erro. {resumo}")
