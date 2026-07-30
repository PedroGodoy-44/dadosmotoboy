#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curl_import.py — importa a sessão do painel a partir de um "Copy as cURL".

DevTools > Network > (requisição do mapa) > botão direito > Copy as cURL.
Cole num arquivo texto e rode:  collector.py --importar-curl curl.txt
"""

import json
import re
import shlex

from .config import CONFIG_PATH, FRESCOR_MIN, INTERVALO, agora


def parse_curl(txt):
    """Converte um comando cURL (bash ou cmd.exe) em dict de requisição."""
    t = re.sub(r"\\\s*\n", " ", txt.strip())
    t = re.sub(r"\^\s*\n", " ", t).replace("\n", " ").strip()
    if t.startswith("curl"):
        t = t[4:]
    try:
        toks = shlex.split(t)
    except ValueError:
        toks = shlex.split(t.replace("'", '"'))

    url, met, hdr, body = None, None, {}, None
    i = 0
    while i < len(toks):
        a = toks[i]
        if a in ("-H", "--header") and i + 1 < len(toks):
            if ":" in toks[i + 1]:
                k, v = toks[i + 1].split(":", 1)
                hdr[k.strip()] = v.strip()
            i += 2
        elif a in ("-X", "--request") and i + 1 < len(toks):
            met = toks[i + 1].upper()
            i += 2
        elif a in ("-d", "--data", "--data-raw", "--data-binary",
                   "--data-ascii", "--data-urlencode") and i + 1 < len(toks):
            body = toks[i + 1]
            i += 2
        elif a in ("-b", "--cookie") and i + 1 < len(toks):
            hdr["Cookie"] = toks[i + 1]
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            if a.startswith("http"):
                url = a
            i += 1
    if not url:
        raise ValueError("URL nao encontrada no cURL.")
    return {"url": url, "metodo": met or ("POST" if body else "GET"),
            "headers": hdr, "body": body}


def importar(arquivo, intervalo=INTERVALO, frescor=FRESCOR_MIN):
    """Lê o arquivo cURL, monta o config.json e o grava. Retorna o cfg."""
    with open(arquivo, encoding="utf-8-sig") as f:
        req = parse_curl(f.read())
    cfg = dict(req, intervalo_seg=intervalo, frescor_min=frescor,
               importado_em=agora().isoformat(timespec="seconds"))
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def carregar_config():
    """Carrega config.json. Retorna None se não existir (o coletor espera)."""
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)
