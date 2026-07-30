#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
presence.py — domínio da presença.

Regras (idênticas ao motor v2):
  - dsStatus traz "Últ. Acesso => Hoje as HH:MM:SS". A presença real se mede
    pela FRESCURA desse acesso, não pela aparição na lista (a lista traz todos).
  - Estados derivados:
      RODANDO  — acesso fresco + tem pedido/rota
      ATIVO    — acesso fresco + se moveu desde o snapshot anterior
      PARADO   — acesso fresco, sem pedido, sem movimento
      AUSENTE  — último acesso mais velho que o limite de frescor
"""

import math
import re
from datetime import timedelta

from .config import MOVIMENTO_M

RE_HOJE = re.compile(r"hoje\s+as\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", re.I)
RE_ONTEM = re.compile(r"ontem\s+as\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", re.I)
RE_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s+as\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", re.I)


def parse_ultimo_acesso(ds_status, ref):
    """Converte dsStatus em datetime. None se nunca acessou / formato novo."""
    if not ds_status:
        return None
    s = str(ds_status)

    m = RE_DATA.search(s)
    if m:
        d, mo, y, hh, mm, ss = m.groups()
        return ref.replace(year=int(y), month=int(mo), day=int(d),
                           hour=int(hh), minute=int(mm),
                           second=int(ss or 0), microsecond=0)

    m = RE_HOJE.search(s)
    if m:
        hh, mm, ss = m.groups()
        return ref.replace(hour=int(hh), minute=int(mm),
                           second=int(ss or 0), microsecond=0)

    m = RE_ONTEM.search(s)
    if m:
        hh, mm, ss = m.groups()
        return (ref - timedelta(days=1)).replace(
            hour=int(hh), minute=int(mm), second=int(ss or 0), microsecond=0)

    return None


def haversine(la1, lo1, la2, lo2):
    """Distância em metros entre dois pontos. None se coordenada inválida."""
    try:
        la1, lo1, la2, lo2 = float(la1), float(lo1), float(la2), float(lo2)
    except (TypeError, ValueError):
        return None
    if 0 in (la1, lo1, la2, lo2):
        return None
    r = 6371000.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = math.radians(la2 - la1)
    dl = math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def derivar_estado(presente, qt, sit, moveu):
    """Deriva o estado operacional a partir dos sinais do snapshot."""
    if not presente:
        return "AUSENTE"
    if qt > 0 or sit not in ("0", "", "None"):
        return "RODANDO"
    if moveu is not None and moveu >= MOVIMENTO_M:
        return "ATIVO"
    return "PARADO"
