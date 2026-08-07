#!/usr/bin/env python3
"""
ler-cookie-firefox.py — extrai o PHPSESSID do painel do perfil do Firefox local.

Existe para evitar o ritual de F12 -> Network -> "Copy as cURL": enquanto voce
estiver logado no painel pelo navegador, a sessao valida ja esta no disco. O
valor sai SO pelo stdout, para ser canalizado por pipe — nunca vira argumento de
comando (apareceria em `ps`) nem e impresso em log.

uso:  python3 scripts/ler-cookie-firefox.py | ...
      MOTOBOYS_FF_PROFILE=/caminho/do/perfil  para apontar outro perfil
"""
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile

HOST = "painel.maisdeliveryempresas.com.br"


def achar_perfil() -> pathlib.Path:
    """Localiza o cookies.sqlite do Firefox.

    O Arch com XDG usa ~/.config/mozilla; instalacoes padrao usam ~/.mozilla.
    Procuramos nos dois e ficamos com o perfil mexido mais recentemente, que e o
    que voce esta usando de fato.
    """
    forcado = os.environ.get("MOTOBOYS_FF_PROFILE")
    if forcado:
        p = pathlib.Path(forcado)
        return p if p.name == "cookies.sqlite" else p / "cookies.sqlite"

    casa = pathlib.Path.home()
    achados = []
    for raiz in (casa / ".config/mozilla/firefox", casa / ".mozilla/firefox"):
        if raiz.is_dir():
            achados += list(raiz.glob("*/cookies.sqlite"))
    if not achados:
        sys.exit("perfil do Firefox nao encontrado — use MOTOBOYS_FF_PROFILE=<caminho>")
    return max(achados, key=lambda f: f.stat().st_mtime)


def main() -> None:
    origem = achar_perfil()
    # O Firefox mantem o banco travado enquanto roda: lemos de uma copia.
    copia = pathlib.Path(tempfile.gettempdir()) / "motoboys-ck.sqlite"
    shutil.copy(origem, copia)
    try:
        con = sqlite3.connect(f"file:{copia}?immutable=1", uri=True)
        linha = con.execute(
            "select value from moz_cookies where host=? and name='PHPSESSID'", (HOST,)
        ).fetchone()
    finally:
        copia.unlink(missing_ok=True)

    if not linha or not linha[0]:
        sys.exit(f"nenhum PHPSESSID de {HOST} no Firefox — faca login no painel antes.")
    sys.stdout.write(linha[0])


if __name__ == "__main__":
    main()
