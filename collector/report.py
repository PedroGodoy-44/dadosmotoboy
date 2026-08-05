#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report.py — análise dos snapshots + saída (console e HTML).

O HTML é gerado com "write-if-changed": só substitui dashboard/html/index.html
quando o conteúdo muda de fato, para que o systemd .path só dispare o deploy
em alteração real.
"""

import hashlib
import json
import os
from collections import defaultdict

from .config import (DASHBOARD_HTML, JANELA, MOVIMENTO_M, PICO, TEMPLATE_PATH,
                     agora)
from .database import gravar_resumo

# Teto de sanidade do deslocamento entre dois snapshots (3 min). Acima disto não
# é moto, é buraco de coleta: `moveu_m` compara com o snapshot ANTERIOR seja ele
# de 3 min ou de 14h atrás (database.py:77-79), então uma queda longa viraria uma
# perna reta de dezenas de km atravessando a cidade.
SALTO_MAX_M = 5000


def analisar(con, dia, escala=None, pico=PICO, janela=JANELA):
    lo, hi = janela
    cur = con.cursor()
    cur.execute("""SELECT hora, COUNT(*), SUM(CASE WHEN erro IS NULL THEN 1 ELSE 0 END)
                   FROM coleta WHERE dia=? GROUP BY hora""", (dia,))
    cob = {h: (t, o or 0) for h, t, o in cur.fetchall()}
    snaps = {h: v[1] for h, v in cob.items() if lo <= h <= hi}
    total = sum(snaps.values())
    if not total:
        return None

    cur.execute("""SELECT id_entregador, COALESCE(nome,id_entregador)
                   FROM snapshot WHERE dia=? GROUP BY id_entregador""", (dia,))
    nomes = dict(cur.fetchall())

    cur.execute("""SELECT id_entregador, hora, SUM(presente)
                   FROM snapshot WHERE dia=? AND hora BETWEEN ? AND ?
                   GROUP BY id_entregador, hora""", (dia, lo, hi))
    grid = defaultdict(dict)
    for mid, h, n in cur.fetchall():
        grid[mid][h] = round(100.0 * (n or 0) / snaps[h], 1) if snaps.get(h) else 0.0

    linhas = []
    for mid, nome in nomes.items():
        cur.execute("""SELECT estado, COUNT(*) FROM snapshot
                       WHERE dia=? AND id_entregador=? AND hora BETWEEN ? AND ?
                       GROUP BY estado""", (dia, mid, lo, hi))
        est = dict(cur.fetchall())
        n_pres = est.get("RODANDO", 0) + est.get("ATIVO", 0) + est.get("PARADO", 0)
        if not n_pres:
            continue
        mins = total and ((hi - lo + 1) * 60 / total) or 3
        cur.execute("""SELECT COUNT(DISTINCT id_pedido) FROM entrega_vista
                       WHERE id_entregador=? AND substr(primeiro_visto,1,10)=?""",
                    (mid, dia))
        peds = cur.fetchone()[0]

        # Tempo de entrega: guardamos SOMA e CONTAGEM, nunca a média. O relatório
        # consolida vários dias, e média de médias mente quando os dias têm pesos
        # diferentes (1 pedido de 60min + 10 de 10min dá 35 na média de médias e
        # 14,5 na conta certa). Cada aba divide na hora e as duas batem.
        # NULLIF(...,0) descarta os dois casos sem medida: o NULL dos pedidos
        # achados por regex no dsPedidos e o 0 de quem veio pela lista dedicada
        # sem nrMinPassados. SUM ignora nulos; COUNT(coluna) só conta não-nulos.
        cur.execute("""SELECT COALESCE(SUM(NULLIF(min_passados,0)),0),
                              COUNT(NULLIF(min_passados,0))
                       FROM entrega_vista
                       WHERE id_entregador=? AND substr(primeiro_visto,1,10)=?""",
                    (mid, dia))
        min_soma, ped_medidos = cur.fetchone()
        base_p = [h for h in range(pico[0], pico[1] + 1) if snaps.get(h)]
        cob_p = [h for h in base_p if grid[mid].get(h, 0) >= 50]

        # início/fim do turno = 1º e último snapshot presente dentro da janela
        cur.execute("""SELECT MIN(ts), MAX(ts) FROM snapshot
                       WHERE dia=? AND id_entregador=? AND presente=1
                         AND hora BETWEEN ? AND ?""", (dia, mid, lo, hi))
        t0, t1 = cur.fetchone()

        item = {
            "id": mid, "nome": nome,
            "inicio": t0[11:16] if t0 else None,
            "fim": t1[11:16] if t1 else None,
            "horas": round(n_pres * mins / 60, 2),
            "h_rodando": round(est.get("RODANDO", 0) * mins / 60, 2),
            "h_parado": round(est.get("PARADO", 0) * mins / 60, 2),
            "pedidos": peds,
            "min_soma": round(min_soma, 1), "ped_medidos": ped_medidos,
            "pico_cob": len(cob_p), "pico_tot": len(base_p),
        }
        item["ocupacao"] = (round(100.0 * item["h_rodando"] / item["horas"], 1)
                            if item["horas"] else 0.0)
        if escala:
            esp = escala.get(nome.strip().lower(), set())
            afer = [h for h in esp if snaps.get(h)]
            if afer:
                cump = [h for h in afer if grid[mid].get(h, 0) >= 50]
                item["escala_h"] = len(afer)
                item["escala_ok"] = len(cump)
                item["aderencia"] = round(100.0 * len(cump) / len(afer), 1)
                item["faltou"] = sorted(set(afer) - set(cump))
        linhas.append(item)

    linhas.sort(key=lambda x: -x["horas"])

    onl = {}
    for h in range(lo, hi + 1):
        if not snaps.get(h):
            onl[str(h)] = None
            continue
        cur.execute("SELECT SUM(presente) FROM snapshot WHERE dia=? AND hora=?", (dia, h))
        onl[str(h)] = round((cur.fetchone()[0] or 0) / snaps[h], 1)

    return {"dia": dia, "snapshots": total,
            "tentativas": sum(t for h, (t, o) in cob.items() if lo <= h <= hi),
            "cobertura": {str(h): snaps.get(h, 0) for h in range(lo, hi + 1)},
            "online_hora": onl, "motoboys": linhas, "tem_escala": bool(escala)}


def trajetos(con, dia, janela=JANELA):
    """Pontos de deslocamento do dia, por motoboy, para a aba Mapa.

    Formato deliberadamente compacto: o HTML é estático e embute 30 dias disto,
    então cada ponto é um array `[minuto_do_dia, lat, lon]` em vez de um objeto
    com chaves repetidas — economiza ~60% do JSON.

    Só entram snapshots com `presente=1`: quando o motoboy está ausente a
    posição é a última conhecida, repetida, e ligá-la no traçado inventaria uma
    parada longa onde ele só sumiu do painel.
    """
    lo, hi = janela
    cur = con.execute("""SELECT id_entregador, COALESCE(nome,id_entregador),
                                ts, lat, lon, moveu_m
                         FROM snapshot
                         WHERE dia=? AND presente=1
                           AND lat IS NOT NULL AND lon IS NOT NULL
                           AND hora BETWEEN ? AND ?
                         ORDER BY id_entregador, ts""", (dia, lo, hi))
    out = {}
    for mid, nome, ts, lat, lon, moveu in cur.fetchall():
        t = out.setdefault(mid, {"nome": nome, "pontos": [], "km": 0.0})
        t["pontos"].append([int(ts[11:13]) * 60 + int(ts[14:16]),
                            round(lat, 5), round(lon, 5)])
        # Abaixo de MOVIMENTO_M é tremido de GPS parado; acima de SALTO_MAX_M é
        # buraco de coleta. Nenhum dos dois é quilômetro rodado de verdade.
        if moveu and MOVIMENTO_M <= moveu < SALTO_MAX_M:
            t["km"] += moveu / 1000.0
    for t in out.values():
        t["km"] = round(t["km"], 1)
    return out


def imprimir(r):
    if not r:
        return print("Sem dados.")
    print(f"\n{'='*84}\n  MOTOBOYS — {r['dia']}  "
          f"({r['snapshots']}/{r['tentativas']} snapshots)\n{'='*84}\n")
    c = (f"{'MOTOBOY':<28}{'HORAS':>7}{'RODANDO':>9}{'PARADO':>8}"
         f"{'OCUP%':>7}{'PED':>5}{'PICO':>7}")
    if r["tem_escala"]:
        c += f"{'ADER':>7}"
    print(c)
    print("-" * len(c))
    for m in r["motoboys"]:
        pk = f"{m['pico_cob']}/{m['pico_tot']}"
        ln = (f"{m['nome'][:27]:<28}{m['horas']:>7.1f}{m['h_rodando']:>9.1f}"
              f"{m['h_parado']:>8.1f}{m['ocupacao']:>7.0f}{m['pedidos']:>5}"
              f"{pk:>7}")
        if r["tem_escala"]:
            a = m.get("aderencia")
            ln += f"{('-' if a is None else f'{a:.0f}%'):>7}"
        print(ln)
    print(f"\n{'HORA':<6}{'PRESENTES':>11}")
    print("-" * 30)
    for h in range(24):
        n = r["online_hora"].get(str(h))
        if n is None:
            continue
        print(f"{h:02d}h{'':<3}{n:>7.1f}  {'#'*int(round(n))}")
    if r["tem_escala"]:
        f = [m for m in r["motoboys"] if m.get("faltou")]
        if f:
            print(f"\n{'='*84}\n  ESCALA x REAL\n{'='*84}")
            for m in f:
                print(f"  {m['nome'][:30]:<32} faltou: "
                      + ", ".join(f"{h:02d}h" for h in m["faltou"]))
    print()


def render_html(payload, destino=DASHBOARD_HTML):
    """Gera o HTML e só grava se mudou (atômico). Retorna (path, mudou:bool)."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    novo = template.replace("__DATA__", json.dumps(payload, ensure_ascii=False))

    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        atual = destino.read_text(encoding="utf-8")
        if hashlib.sha256(atual.encode()).digest() == \
           hashlib.sha256(novo.encode()).digest():
            return destino, False

    tmp = destino.with_suffix(".html.tmp")
    tmp.write_text(novo, encoding="utf-8")
    os.replace(tmp, destino)                        # troca atômica
    return destino, True


def gerar(con, dia=None):
    """Monta o payload de todos os dias (ou de um) e escreve o HTML."""
    from .escala import carregar_escala, escala_dia

    esc = carregar_escala()
    dias = [dia] if dia else [r[0] for r in con.execute(
        "SELECT DISTINCT dia FROM coleta ORDER BY dia DESC LIMIT 30")]
    pay = {"gerado_em": f"{agora():%d/%m/%Y %H:%M}", "dias": {}}
    for d in dias:
        res = analisar(con, d, escala_dia(esc, d) if esc else None)
        if res:
            res["trajetos"] = trajetos(con, d)
            pay["dias"][d] = res
            gravar_resumo(con, d, res["motoboys"])
    if not pay["dias"]:
        return None, None, False
    primeiro = dias[0] if dias and dias[0] in pay["dias"] else next(iter(pay["dias"]))
    imprimir(pay["dias"][primeiro])
    path, mudou = render_html(pay)
    return pay, path, mudou
