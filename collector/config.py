#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — caminhos (pathlib), constantes e logging do coletor.

Toda a árvore de arquivos é derivada de BASE (a raiz do projeto), nunca do CWD.
Isso permite rodar como serviço systemd de qualquer diretório sem quebrar.
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:                                   # pragma: no cover
    TZ = None

# ── Árvore de diretórios ────────────────────────────────────────────────
COLLECTOR_DIR = Path(__file__).resolve().parent          # ~/projetos/motoboys/collector
BASE = COLLECTOR_DIR.parent                              # ~/projetos/motoboys

CONFIG_PATH = COLLECTOR_DIR / "config.json"
DB_PATH = COLLECTOR_DIR / "database.db"
ESCALA_PATH = COLLECTOR_DIR / "escala.csv"
TEMPLATE_PATH = COLLECTOR_DIR / "templates" / "report.html"
LOG_DIR = COLLECTOR_DIR / "logs"
AMOSTRA_PATH = COLLECTOR_DIR / "_amostra_mapa.json"

DASHBOARD_HTML = BASE / "dashboard" / "html" / "index.html"

ENV_PATH = BASE / ".env"

# ── Constantes de negócio (idênticas ao motor original v2) ──────────────
INTERVALO = 180          # segundos entre snapshots
FRESCOR_MIN = 10         # até N min de defasagem = considerado presente
MOVIMENTO_M = 60         # metros mínimos p/ contar como deslocamento
PICO = (18, 22)          # janela de pico (hora inicial, hora final)
JANELA = (8, 23)         # janela de presença (hora inicial, hora final inclusive)


def agora():
    """Datetime timezone-aware em America/Sao_Paulo (ou naive como fallback)."""
    return datetime.now(TZ) if TZ else datetime.now()


def carregar_env(path=ENV_PATH):
    """Carrega variáveis de um .env simples (KEY=VALUE) para os.environ.

    Não sobrescreve variáveis já presentes no ambiente. Tokens NUNCA são
    logados nem versionados — este arquivo é gitignored.
    """
    if not path.exists():
        return
    for linha in path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


# ── Logging: arquivo rotativo + stdout (journald captura o stdout) ──────
_LOGGER_PRONTO = False


def get_logger(nome="motoboys"):
    global _LOGGER_PRONTO
    logger = logging.getLogger(nome)
    if _LOGGER_PRONTO:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        LOG_DIR / "collector.log", maxBytes=2_000_000, backupCount=5,
        encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()                    # journald pega isto
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    _LOGGER_PRONTO = True
    return logger
