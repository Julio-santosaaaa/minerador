Meu nome é Julio.

## PROJETO MINERADOR

Sistema em Python que garimpa ofertas **low ticket** na Biblioteca de Anúncios da Meta (BR).
O Playwright abre a biblioteca pública, captura o GraphQL interno da Meta, agrupa os anúncios
em "ofertas", ranqueia por **calor** (sinal de que está escalando) e joga tudo num banco do
Notion pra revisão manual.

- Rodar: `scripts/run.sh run` (ou `.venv/bin/python -m minerador run`)
- Teste sem Notion: `scripts/run.sh run --keyword "planilha financeira" --dry-run`
- Config (palavras-chave, pesos do calor): `config.yaml`
- Segredos: `.env` (`NOTION_TOKEN`, `NOTION_PARENT_PAGE_ID`)
- Histórico local: `data/minerador.db` (SQLite)
- Não é repo git. Passo a passo no `README.md`.
