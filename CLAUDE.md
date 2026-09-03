Meu nome é Julio.

## PROJETO MINERADOR

Sistema em Python que garimpa ofertas **low ticket** na Biblioteca de Anúncios da Meta (BR).
O Playwright abre a biblioteca pública, captura o GraphQL interno da Meta, agrupa os anúncios
em "ofertas", ranqueia por **calor** (sinal de que está escalando) e joga tudo num banco do
Notion pra revisão manual.

- Rodar: `scripts/run.sh run` · tracker: `scripts/run.sh recalc` · acompanhar: `--progress`
- Teste sem Notion: `scripts/run.sh run --target 3 --dry-run`
- Config: `config.yaml` · segredos: `.env` (`NOTION_TOKEN`)
- Estado: `data/minerador.db` (SQLite, versionado — dedup/histórico/reciclagem)
- Filtro forte: `minerador/salespage.py` abre a página de vendas antes de validar
- **Nuvem**: GitHub Actions roda todo dia 06h BRT (`.github/workflows/minerador.yml`).
  Repo: github.com/Julio-santosaaaa/minerador (público). Setup: `SETUP-GITHUB.md`.
