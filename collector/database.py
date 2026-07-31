#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database.py — persistência SQLite (WAL, anti-corrupção).

Esquema idêntico ao motor v2:
  snapshot      — 1 linha por (ts, entregador): frescor, presença, estado, mov.
  coleta        — 1 linha por tentativa de coleta (http, contagens, erro)
  entrega_vista — vínculo operacional pedido↔entregador (sem dados do cliente)
"""

import re
import sqlite3

from .config import DB_PATH, FRESCOR_MIN, agora
from .presence import derivar_estado, haversine, parse_ultimo_acesso

RE_PEDIDO = re.compile(r"#(\d{6,})")


def db_init(path=DB_PATH):
    """Abre (criando se preciso) o banco. WAL + PRAGMAs de robustez.

    WAL permite 1 escritor (coletor) e N leitores (relatório) concorrentes sem
    corromper. busy_timeout evita 'database is locked' em picos.
    """
    con = sqlite3.connect(str(path), timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("""CREATE TABLE IF NOT EXISTS snapshot(
        ts TEXT, dia TEXT, hora INTEGER, id_entregador TEXT, nome TEXT,
        ultimo_acesso TEXT, defasagem_min REAL, presente INTEGER,
        lat REAL, lon REAL, moveu_m REAL, qt_pedidos INTEGER,
        id_situacao TEXT, estado TEXT,
        PRIMARY KEY (ts, id_entregador))""")
    con.execute("""CREATE TABLE IF NOT EXISTS coleta(
        ts TEXT PRIMARY KEY, dia TEXT, hora INTEGER,
        http INTEGER, n_lista INTEGER, n_presente INTEGER, erro TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS entrega_vista(
        id_pedido TEXT, id_entregador TEXT, id_situacao TEXT,
        min_passados INTEGER, primeiro_visto TEXT, ultimo_visto TEXT,
        PRIMARY KEY (id_pedido, id_entregador))""")
    con.execute("""CREATE TABLE IF NOT EXISTS resumo_diario(
        dia TEXT, id_entregador TEXT, nome TEXT,
        inicio TEXT, fim TEXT,
        horas REAL, h_rodando REAL, h_parado REAL,
        pedidos INTEGER, ocupacao REAL,
        atualizado_em TEXT,
        PRIMARY KEY (dia, id_entregador))""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_dia ON snapshot(dia, id_entregador)")
    con.commit()
    return con


def gravar(con, ts, registros, frescor_min=FRESCOR_MIN, entregas=None):
    """Grava um snapshot completo. Retorna nº de presentes."""
    dia, hora, iso = f"{ts:%Y-%m-%d}", ts.hour, ts.isoformat(timespec="seconds")
    n_pres = 0

    for r in registros:
        if not isinstance(r, dict):
            continue
        mid = str(r.get("idEntregador") or r.get("identregador") or "")
        if not mid:
            continue
        nome = r.get("dsNome")
        lat, lon = r.get("nrLatitude"), r.get("nrLongitude")
        qt = int(r.get("qtPedidos") or 0)
        sit = str(r.get("idSituacao") or "0")

        ua = parse_ultimo_acesso(r.get("dsStatus"), ts)
        defas = (ts - ua).total_seconds() / 60 if ua else None
        presente = 1 if (defas is not None and defas <= frescor_min) else 0

        # deslocamento desde o snapshot anterior desse entregador
        prev = con.execute("""SELECT lat, lon FROM snapshot WHERE id_entregador=?
                              ORDER BY ts DESC LIMIT 1""", (mid,)).fetchone()
        moveu = haversine(prev[0], prev[1], lat, lon) if prev else None

        estado = derivar_estado(presente, qt, sit, moveu)
        n_pres += presente

        con.execute("INSERT OR REPLACE INTO snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (iso, dia, hora, mid, nome,
                     ua.isoformat(timespec="seconds") if ua else None,
                     defas, presente,
                     float(lat) if lat else None, float(lon) if lon else None,
                     moveu, qt, sit, estado))

        # sempre extrai o #id do texto: a lista dedicada costuma vir PARCIAL
        # (só alguns motoboys), e o dsPedidos é a única fonte para o resto.
        # A lista 3 roda depois e sobrescreve com o dado melhor (ver _reg_entrega).
        for pid in RE_PEDIDO.findall(str(r.get("dsPedidos") or "")):
            _reg_entrega(con, pid, mid, sit, None, iso)

    # lista 3: entregas em curso (dsNome ali é o CLIENTE — não gravamos)
    for e in (entregas or []):
        _reg_entrega(con, str(e.get("idPedido")), str(e.get("idEntregador")),
                     str(e.get("idSituacao") or ""), e.get("nrMinPassados"), iso)
    return n_pres


def _reg_entrega(con, pid, mid, sit, minutos, iso):
    if not pid or not mid:
        return
    con.execute("""INSERT INTO entrega_vista VALUES (?,?,?,?,?,?)
                   ON CONFLICT(id_pedido,id_entregador) DO UPDATE SET
                     ultimo_visto  = excluded.ultimo_visto,
                     id_situacao   = excluded.id_situacao,
                     min_passados  = MAX(COALESCE(entrega_vista.min_passados,0),
                                         COALESCE(excluded.min_passados,0))""",
                (pid, mid, sit, minutos, iso, iso))


def gravar_resumo(con, dia, linhas):
    """Persiste o resumo diário (1 linha por motoboy) calculado por report.analisar.

    Upsert idempotente: reexecutar o relatório do mesmo dia só atualiza os valores.
    Guarda início/fim do turno e as horas, para o histórico sobreviver à limpeza
    de snapshots antigos.
    """
    ts = agora().isoformat(timespec="seconds")
    for m in linhas:
        con.execute("INSERT OR REPLACE INTO resumo_diario VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (dia, m["id"], m["nome"], m.get("inicio"), m.get("fim"),
                     m["horas"], m["h_rodando"], m["h_parado"],
                     m["pedidos"], m["ocupacao"], ts))
    con.commit()


def registrar_coleta(con, ts, http, n_lista, n_presente, erro):
    con.execute("INSERT OR REPLACE INTO coleta VALUES (?,?,?,?,?,?,?)",
                (ts.isoformat(timespec="seconds"), f"{ts:%Y-%m-%d}",
                 ts.hour, http, n_lista, n_presente, erro))
    con.commit()
