#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
panel.py — camada HTTP do painel Mais Delivery (ajax_operacao.php).

Faz a requisição autenticada por cookie de sessão e separa o retorno em:
  - motoboys : registros com dsStatus ("Últ. Acesso => ...")
  - entregas : registros com idPedido + idEntregador (dsNome = CLIENTE)

O retorno pode vir como JSON puro ou como a PÁGINA HTML com arrays embutidos.
"""

import json
import re
import sys

try:
    import requests
except ImportError:                                 # pragma: no cover
    sys.exit("Falta 'requests'. Arch: sudo pacman -S python-requests "
             "(ou use a venv: pip install requests)")


def fetch(cfg):
    """Executa a requisição. Retorna (http_status, data|None, erro|None)."""
    try:
        r = requests.request(
            cfg["metodo"], cfg["url"], headers=cfg["headers"],
            data=cfg["body"].encode() if cfg.get("body") else None,
            timeout=25)
    except Exception as e:
        return 0, None, f"{type(e).__name__}: {e}"
    if r.status_code in (401, 403):
        return r.status_code, None, "SESSAO_EXPIRADA"
    if r.status_code >= 400:
        return r.status_code, None, f"HTTP {r.status_code}"
    txt = r.text.strip()
    try:
        return r.status_code, r.json(), None
    except Exception:
        pass
    # Não é JSON: pode ser a PÁGINA HTML com os dados embutidos, ou o login.
    if "dsStatus" in txt or "idEntregador" in txt:
        return r.status_code, {"__html__": txt}, None
    if "login" in txt.lower() or "<html" in txt[:300].lower():
        return r.status_code, None, "SESSAO_EXPIRADA"
    return r.status_code, None, f"nao-JSON: {txt[:150]}"


RE_ARRAY = re.compile(r"\[\s*\{.*?\}\s*\]", re.S)


def json_do_html(txt):
    """Extrai arrays JSON embutidos no HTML da página."""
    out = []
    for m in RE_ARRAY.finditer(txt):
        bruto = m.group(0)
        for tentativa in (bruto, bruto.replace("\\/", "/")):
            try:
                v = json.loads(tentativa)
            except Exception:
                continue
            if isinstance(v, list) and v and isinstance(v[0], dict):
                out.append(v)
            break
    return out


def _listas(data):
    """Devolve todas as listas de dicts encontradas na resposta."""
    out = []
    if isinstance(data, dict) and "__html__" in data:
        return json_do_html(data["__html__"])
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            out.append(data)
    elif isinstance(data, dict):
        for v in data.values():
            out.extend(_listas(v))
    return out


def classificar(data):
    """Separa as listas do retorno por formato:
       - entregador:  tem dsStatus ("Últ. Acesso => ...")
       - entrega:     tem idPedido + idEntregador (dsNome = CLIENTE, não motoboy)
       - estabelec.:  não tem idEntregador (ignorado)
    """
    motoboys, entregas = [], []
    for lst in _listas(data):
        for r in lst:
            if not isinstance(r, dict):
                continue
            if r.get("dsStatus"):
                motoboys.append(r)
            elif r.get("idPedido") and r.get("idEntregador"):
                entregas.append(r)
    return motoboys, entregas
