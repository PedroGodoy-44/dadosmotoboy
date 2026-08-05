#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mock.py — gera dados sintéticos para testar o pipeline inteiro sem o painel.
Reproduz o formato real do retorno (dsStatus, entregas com dsNome=cliente).
"""

from datetime import timedelta

from .config import ESCALA_PATH, agora, get_logger
from .database import db_init, gravar, registrar_coleta

log = get_logger()


def gerar_mock():
    import random
    random.seed(3)
    con = db_init()
    for t in ("snapshot", "coleta", "entrega_vista"):
        con.execute(f"DELETE FROM {t}")

    eq = [("67325", "Allafi Davi da Silva Ferreira", (18, 23), 0.30, 0.10),
          ("68841", "Marcos Machado de Oliveira", (10, 23), 0.95, 0.75),
          ("71585", "Igor Pereira", (11, 16), 0.90, 0.60)]
    clientes = ["Jake Matheo Nogueira", "Ana Paula Reis", "Carlos Souza"]
    lojas = ["MilkShow", "Casa de Carnes Dini", "Padaria Macaubas", "Restaurante Villa Cintra"]
    # O painel nao devolve duracao: o tempo de entrega sai de ver o MESMO pedido
    # em varios ciclos mudando de status. Um pedido descartavel por ciclo nao
    # exercitaria nada disso, entao aqui eles vivem de 5 a 12 ciclos (15 a 36
    # min) e progridem "Em andamento" -> "Pronto pra Entrega" -> "Saiu para
    # entrega", como o painel real faz.
    def status(idade):
        return ("Em andamento" if idade < 2
                else "Pronto pra Entrega" if idade < 4
                else "Saiu para entrega" if idade < 7
                else "Entregador na sua porta")

    base = agora().replace(hour=0, minute=0, second=0, microsecond=0)
    pid = 63300000
    for dsc in (1, 0):
        d0 = base - timedelta(days=dsc)
        ativos = {mid: [] for mid, *_ in eq}       # mid -> [[pid, loja, idade, vida]]
        for p in range(int(8 * 20), int(24 * 20)):
            ts = d0 + timedelta(minutes=3 * p)
            regs, entregas = [], []
            for mid, nm, (i, f), fid, ocu in eq:
                dentro = i <= ts.hour < f
                if dentro and random.random() < fid:
                    ua = ts - timedelta(seconds=random.randint(0, 300))
                    fila = ativos[mid]
                    for ped in fila:
                        ped[2] += 1
                    fila[:] = [ped for ped in fila if ped[2] <= ped[3]]
                    if len(fila) < 2 and random.random() < ocu:
                        pid += 1
                        fila.append([pid, random.choice(lojas), 0, random.randint(5, 12)])
                    for pd, loja, idade, _ in fila:
                        if status(idade) == "Saiu para entrega":
                            entregas.append({      # lista 3: dsNome = CLIENTE
                                "dsNome": random.choice(clientes),
                                "idPedido": str(pd), "idEntregador": mid,
                                "idSituacao": "5",
                                "nrLatitude": "-21.38435305",
                                "nrLongitude": "-46.53368242"})
                    texto = "".join(f"<br/>{loja} #{pd} {status(idade)}.</br>"
                                    for pd, loja, idade, _ in fila)
                    regs.append({
                        "idEntregador": mid, "dsNome": nm,
                        "nrLatitude": f"{-21.37 + random.uniform(-.02,.02):.8f}",
                        "nrLongitude": f"{-46.52 + random.uniform(-.02,.02):.8f}",
                        "idSituacao": "5" if fila else 0,
                        "qtPedidos": len(fila),
                        "dsPedidos": texto or "Sem pedido no momento",
                        "dsStatus": f"Últ. Acesso => Hoje as {ua:%H:%M:%S}",
                        "nrKMDistancia": 0})
                else:
                    ua = ts - timedelta(minutes=random.randint(40, 400))
                    regs.append({
                        "idEntregador": mid, "dsNome": nm,
                        "nrLatitude": "-21.37000000", "nrLongitude": "-46.52000000",
                        "idSituacao": 0, "qtPedidos": 0,
                        "dsPedidos": "Sem pedido no momento",
                        "dsStatus": f"Últ. Acesso => Hoje as {ua:%H:%M:%S}",
                        "nrKMDistancia": 0})
            n = gravar(con, ts, regs, entregas=entregas)
            registrar_coleta(con, ts, 200, len(regs), n, None)
        con.commit()
    if not ESCALA_PATH.exists():
        with open(ESCALA_PATH, "w", encoding="utf-8") as f:
            f.write("motoboy,dia,inicio,fim\n")
            for _, nm, (i, fm), _, _ in eq:
                f.write(f"{nm},*,{i},{fm}\n")
    log.info("mock gerado")
    return con
