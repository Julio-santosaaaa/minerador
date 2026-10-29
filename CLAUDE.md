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
- **Nuvem**: GitHub Actions roda 2x por dia (06h e 13h BRT) (`.github/workflows/minerador.yml`):
  **4 jobs em paralelo** (`MINERADOR_JOB`/`MINERADOR_JOBS`, cada um com sua fatia das palavras-chave,
  até 315 min) + 1 job `merge` (`python -m minerador merge`) que junta o estado, dá a **nota 1-10**
  (6 critérios + média, Groq grátis, `GROQ_API_KEY`) e comita. A rodada só para por TEMPO
  (meta 20 novas, continua depois); passadas de scroll 24→40→60 + busca por frases das ofertas boas.
  Sem repetidas: oferta enviada/apagada-do-Notion/rejeitada (14d) não volta (tabelas `synced`, `blocked`, `rejected`).
  Testes: `python3 -m pytest tests -q`.
  Repo: github.com/Julio-santosaaaa/minerador (público). Setup: `SETUP-GITHUB.md`.
