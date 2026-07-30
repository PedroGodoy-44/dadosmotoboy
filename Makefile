# Makefile — atalhos do projeto Motoboys.
.PHONY: install run stop status deploy logs update backup mock report import test help

PY := .venv/bin/python

help:
	@echo "make install  - instala tudo (venv, deps, banco, systemd, start)"
	@echo "make run      - inicia coletor + timer + watcher"
	@echo "make stop     - para os servicos"
	@echo "make status   - status do coletor/timer/watcher"
	@echo "make deploy   - publica o dashboard no Cloudflare Pages"
	@echo "make logs     - segue o log do coletor (journald)"
	@echo "make update   - atualiza codigo/deps e reinicia"
	@echo "make backup   - backup consistente do banco + config"
	@echo "make mock     - gera dados sinteticos e o relatorio"
	@echo "make report   - regenera o relatorio HTML"

install:
	./scripts/install.sh

run:
	./scripts/start.sh

stop:
	./scripts/stop.sh

status:
	./scripts/status.sh

deploy:
	./scripts/deploy.sh

logs:
	journalctl --user -u motoboys-collector -f

update:
	./scripts/update.sh

backup:
	./scripts/backup.sh

mock:
	$(PY) -m collector.collector --mock --relatorio

report:
	$(PY) -m collector.collector --relatorio

import:
	@test -n "$(CURL)" || (echo "uso: make import CURL=curl.txt" && exit 1)
	$(PY) -m collector.collector --importar-curl $(CURL)

test:
	$(PY) -m collector.collector --testar
