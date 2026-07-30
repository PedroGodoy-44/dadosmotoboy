# Motoboys — Presença Real (Mais Delivery)

Rastreia a **presença real dos motoboys** da plataforma Mais Delivery: tira
snapshots periódicos do painel web (sessão capturada via "Copy as cURL"), deriva
o estado de cada entregador pela frescura do último acesso, grava em SQLite e
gera um dashboard HTML com presença por hora e aderência à escala declarada.

Roda 100% no **Arch Linux** via **systemd** (sem Windows, sem cron), inicia sozinho
no boot, sobrevive a logout/reboot e publica o dashboard no **Cloudflare Pages**
automaticamente sempre que o HTML muda.

```
coletor (loop 3min)  ─►  SQLite  ─►  relatório (HTML)  ─►  Cloudflare Pages
   systemd service        WAL         systemd .timer         systemd .path → deploy
```

**Estados derivados:** `RODANDO` (fresco + pedido) · `ATIVO` (fresco + moveu) ·
`PARADO` (fresco, parado) · `AUSENTE` (último acesso velho demais).

---

## Instalação (1 comando)

```bash
cd ~/projetos/motoboys
./install.sh
```

Faz tudo: cria a `.venv`, instala dependências, inicializa o banco, instala e
habilita as units systemd de usuário, liga o *linger* (sobrevive a logout) e
inicia o coletor. **Nunca usa sudo.**

### Pré-requisitos
- Python 3.11+ (testado em 3.14) — já presente.
- **Node.js + npm** *(só para o deploy no Cloudflare)*:
  ```bash
  sudo pacman -S nodejs npm      # rode você mesmo; o install.sh não usa sudo
  ```
  Sem Node, todo o resto funciona; só o deploy fica inativo.

---

## Ligar a sessão do painel (para coletar dados reais)

O coletor sobe já no `install.sh`, mas fica **esperando** a sessão do painel (ele
avisa no log e não quebra). Para alimentá-lo:

1. Abra o painel Mais Delivery no Firefox → **F12 → Network**.
2. Ache a requisição do mapa/operação (`ajax_operacao.php`), botão direito →
   **Copy → Copy as cURL** → cole num arquivo `curl.txt`.
3. Importe e teste:
   ```bash
   make import CURL=curl.txt      # grava collector/config.json
   make test                      # 1 requisição + prévia dos entregadores
   ```
4. O coletor passa a gravar snapshots sozinho no próximo ciclo (a cada 3 min).

Quando a sessão expirar, o log mostra `SESSAO_EXPIRADA` — repita os passos 1–3.

---

## Deploy no Cloudflare Pages

1. Preencha o `.env` (criado pelo install a partir do `.env.example`):
   ```
   CLOUDFLARE_API_TOKEN=...     # Dashboard > API Tokens > "Cloudflare Pages: Edit"
   CLOUDFLARE_ACCOUNT_ID=...
   CF_PAGES_PROJECT=motoboys
   ```
2. Instale o wrangler local (uma vez):
   ```bash
   cd cloudflare && npm install && cd ..
   ```
3. Publique:
   ```bash
   make deploy
   ```
   No primeiro deploy o **projeto Pages é criado** automaticamente. O comando
   imprime a URL pública ao final.

**Automático:** o `motoboys-report.timer` regenera o HTML a cada 5 min; quando o
conteúdo muda, o `motoboys-deploy.path` dispara o deploy sozinho. Nenhuma ação
manual é necessária depois de configurado.

> Tokens vivem **só** no `.env` (gitignored). Nunca são versionados nem logados.

---

## Comandos úteis

```bash
make status                                   # coletor + timer + watcher
make logs                                     # log do coletor ao vivo (journald)
make mock                                     # dados sintéticos + relatório (sem painel)
make report                                   # regenera o HTML agora
make deploy                                   # publica no Cloudflare
make backup                                   # backup consistente do banco
make update                                   # atualiza deps + reinicia

systemctl --user list-timers | grep motoboys  # próxima geração de relatório
journalctl --user -u motoboys-deploy -n 50    # histórico de deploys
```

Atalhos equivalentes na raiz: `./start.sh` `./stop.sh` `./status.sh`
`./update.sh` `./deploy.sh` `./install.sh`.

---

## Atualização

```bash
make update      # git pull (se repo) + pip upgrade + reinstala units + restart
```

## Backup e recuperação

```bash
make backup      # gera backups/motoboys-AAAAMMDD-HHMMSS.tar.gz (mantém os 14 últimos)
```
O backup usa a API `.backup`/`VACUUM INTO` do SQLite (snapshot consistente mesmo
com o coletor escrevendo). Contém `database.db`, `config.json` e `escala.csv` —
**nunca** o `.env`.

**Recuperar:**
```bash
systemctl --user stop motoboys-collector
tar -xzf backups/motoboys-AAAAMMDD-HHMMSS.tar.gz -C collector/
systemctl --user start motoboys-collector
```

---

## Estrutura do projeto

```
collector/     motor Python (camadas): config, presence(domínio), panel(HTTP),
               database(SQLite/WAL), escala, report, mock, collector(CLI)
  templates/   report.html (template do dashboard)
dashboard/     html/index.html = saída publicada; scripts/generate.sh
cloudflare/    wrangler.toml + package.json (wrangler local)
scripts/       install/start/stop/status/deploy/update/backup .sh
systemd/       units (.service/.timer/.path) com placeholder %BASE%
Makefile · README.md · .env.example
```

Runtime (gitignored): `.venv/`, `collector/config.json`, `collector/database.db*`,
`collector/escala.csv`, `collector/logs/`, `dashboard/html/index.html`, `backups/`,
`.env`, `cloudflare/node_modules/`.

---

## systemd (units de usuário)

| Unit | Papel |
|------|-------|
| `motoboys-collector.service` | Coletor long-running. `Restart=always`, `RestartSec=5`. |
| `motoboys-report.timer` → `.service` | Regenera o HTML a cada 5 min (`Persistent=true`). |
| `motoboys-deploy.path` → `.service` | Observa o HTML; deploya quando muda. |

Logs vão para o **journald** (`journalctl --user -u motoboys-collector`) e também
para `collector/logs/collector.log` (rotativo, ~2 MB × 5). O SQLite roda em **WAL**
(`synchronous=NORMAL`, `busy_timeout=5000`) para leitura/escrita concorrente sem
corromper.

> **Alternativa (timer no lugar do serviço):** dá para trocar o serviço
> long-running por um `.timer` chamando `--coletar --uma-vez` a cada 3 min. Foi
> preferido o serviço porque casa com `Restart=always`/`RestartSec=5` e o motor já
> tem loop próprio.

---

## Troubleshooting

- **`SESSAO_EXPIRADA` no log** → recapture o cURL e `make import CURL=curl.txt`.
- **`sem config.json` no log** → o coletor está esperando; faça a importação do cURL.
- **Deploy não roda** → falta Node/wrangler (`sudo pacman -S nodejs npm` +
  `cd cloudflare && npm install`) ou faltam tokens no `.env`.
- **Serviço não sobe no boot** → confira `loginctl show-user $USER -p Linger`
  (deve ser `Linger=yes`) e `systemctl --user is-enabled motoboys-collector`.
- **Fuso horário** → o código usa `America/Sao_Paulo`; `Brazil/East` é equivalente.
```
