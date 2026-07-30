#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
escala.py — escala declarada (opcional). CSV: motoboy,dia,inicio,fim
  dia = YYYY-MM-DD | seg,ter,qua,qui,sex,sab,dom | * (todos)
Usada para medir aderência (escala x presença real).
"""

from collections import defaultdict
from datetime import datetime

from .config import ESCALA_PATH

DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def carregar_escala(path=ESCALA_PATH):
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.lower().startswith("motoboy"):
                continue
            p = [x.strip() for x in ln.split(",")]
            if len(p) < 4:
                continue
            try:
                out.append({"nome": p[0], "dia": p[1].lower(),
                            "ini": int(p[2].split(":")[0]),
                            "fim": int(p[3].split(":")[0])})
            except ValueError:
                pass
    return out


def escala_dia(escala, dia):
    d = datetime.strptime(dia, "%Y-%m-%d").date()
    dsem = DIAS[d.weekday()]
    out = defaultdict(set)
    for e in escala:
        if e["dia"] in ("*", "todos", dsem, dia):
            for h in range(e["ini"], max(e["ini"] + 1, e["fim"])):
                out[e["nome"].strip().lower()].add(h % 24)
    return out
