# Minerador 20+ ofertas/dia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4 jobs paralelos no Actions minerando ≥20 ofertas novas/dia até o fim do tempo, sem repetidas, com 7 colunas de nota (Gemini grátis) no Notion.

**Architecture:** O `run` existente ganha fatiamento por job (`MINERADOR_JOB`/`MINERADOR_JOBS`), passadas de scroll crescentes, memória de rejeitadas e parada só por tempo. O workflow vira matrix de 4 jobs que gravam cada um num SQLite próprio (artifact) e um job `merge` junta o estado, dá as notas via Gemini e faz commit.

**Tech Stack:** Python 3.11, Playwright, SQLite, notion-client, `google-genai` (Gemini), GitHub Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-minerador-20-ofertas-design.md`

## Global Constraints

- Nenhuma coluna atual do Notion é alterada; só se adicionam 7: `NOTA MÉDIA`, `Dor forte`, `Promessa desejável`, `Público comprador`, `Transformação clara`, `Valor percebido`, `Facilidade de compra` (todas `number`).
- Notas de 1 a 10; nunca inventadas: erro/limite/sem texto → colunas vazias. `NOTA MÉDIA` só se as 6 vieram.
- 1ª passada de cada job: `max_scrolls` 24, 1 aba, pausas 3.0–6.5 s (iguais a hoje). Passadas seguintes: 40 e 60 scrolls.
- `run_deadline_min: 315`; `timeout-minutes: 345`; 4 jobs; `fail-fast: false`; `continue-on-error` nos jobs de mineração.
- Modelo Gemini padrão `gemini-2.5-flash-lite`, configurável em `config.yaml` (`gemini_model`). Segredo `GEMINI_API_KEY`.
- Rejeição dura vale 14 dias; "não abriu a página" vale 2 dias.
- Já implementado em 2026-10-29 (não refazer): `recycle_days: 0`, tabela `blocked`, `known_pages_and_domains`, `root_domain`, filtros de coaching, palavras-chave de nicho iniciais (210).

## Review Focus

- Dois jobs validam a mesma oferta ao mesmo tempo → não pode criar duas páginas no Notion.
- Um job é bloqueado pela Meta no meio → os outros 3 terminam e o merge ainda comita.
- `GEMINI_API_KEY` ausente ou 429 → ofertas sobem sem nota, sem erro fatal.
- Resposta do Gemini fora do formato ou nota fora de 1–10 → coluna vazia.
- Fatia de palavras-chave vazia (jobs > palavras) → job termina limpo.

## File Structure

- `minerador/store.py` — tabela `rejected` + helpers. 
- `minerador/slicing.py` (novo) — fatiamento estável de palavras-chave por job.
- `minerador/nota.py` (novo) — prompt, chamada Gemini, parsing, média.
- `minerador/__main__.py` — passadas, parada por tempo, snowball, uso de rejeitadas, fatia.
- `minerador/notion_sync.py`, `minerador/notion_setup.py` — colunas e escrita das notas; dedup cross-job.
- `minerador/merge.py` (novo) — junta bancos dos jobs, nota, sync final.
- `config.yaml`, `.github/workflows/minerador.yml`, `requirements.txt`, `SETUP-GITHUB.md`, `CLAUDE.md`.
- `tests/` (novo): `test_store_rejected.py`, `test_slicing.py`, `test_nota.py`, `test_merge.py`.

---

### Task 1: Memória de rejeitadas

**Files:** Modify `minerador/store.py`, `minerador/__main__.py` (`_process_pool`); Test `tests/test_store_rejected.py`

**Interfaces:**
- Produces: `store.reject(conn, page_id: str, domain: str, reason: str, hard: bool) -> None`; `store.rejected_sets(conn) -> tuple[set[str], set[str]]` (page_ids, root_domains ainda válidos: hard 14 dias, soft 2 dias).

- [ ] **Step 1: testes** — `test_hard_reject_blocks_within_14_days` (reject hard hoje → `page_id` e `root_domain(domain)` em `rejected_sets`), `test_soft_reject_expires_after_2_days` (inserir `rejected_at` de 3 dias atrás com `hard=0` → ausente), `test_hard_reject_expires_after_14_days`.
- [ ] **Step 2:** `pytest tests/test_store_rejected.py -v` → FAIL.
- [ ] **Step 3:** Tabela `rejected(page_id TEXT, domain_root TEXT, reason TEXT, hard INTEGER, rejected_at TEXT, PRIMARY KEY(page_id, domain_root))` no `SCHEMA`; implementar `reject` (upsert) e `rejected_sets` (filtra por idade em Python usando `now_iso`).
- [ ] **Step 4:** Em `_process_pool`, ao receber `not v.ok`: `store.reject(..., hard=True)` salvo se o motivo for "sem preço…" (soft); quando `open_salespage` retorna vazio: `hard=False`. Antes do loop, filtrar `cands` por `rejected_sets`. Passar os sets como `known_pages`/`known_domains` já existentes (unir).
- [ ] **Step 5:** pytest PASS; commit `feat: memória de páginas rejeitadas`.

### Task 2: Fatiamento por job e 400+ palavras-chave

**Files:** Create `minerador/slicing.py`; Modify `minerador/config.py`, `config.yaml`; Test `tests/test_slicing.py`

**Interfaces:**
- Produces: `slicing.slice_for_job(keywords: list[str], job: int, jobs: int) -> list[str]` (embaralha com `random.Random(len(keywords))` fixo e devolve os itens com `i % jobs == job`; `jobs<=1` devolve a lista original).

- [ ] **Step 1: testes** — `test_slices_are_disjoint_and_complete` (união das 4 fatias == lista, interseções vazias), `test_slice_is_stable_across_calls`, `test_empty_slice_ok` (3 palavras, 4 jobs → uma fatia vazia sem erro), `test_single_job_returns_original`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. 
- [ ] **Step 4:** `Config` lê `MINERADOR_JOB` (default 0) e `MINERADOR_JOBS` (default 1) e aplica `slice_for_job` em `keywords` e `keywords_reserve`; `kw_cursor` passa a `kw_cursor_{job}`. Em `config.yaml`, acrescentar ≥ 200 palavras em `keywords_niche_pt/es/en` (total ≥ 400 no pool): long-tail de nicho com formato digital (ex.: "planilha de custos para confeiteira", "apostila de inglês para crianças", "pack de artes para igreja"), sem termos de curso/coaching/renda extra/físicos.
- [ ] **Step 5:** pytest PASS; `python -c "from minerador.config import Config; print(len(Config.load().keywords))"` ≥ 400; commit.

### Task 3: Passadas, parada só por tempo e envio de tudo

**Files:** Modify `minerador/__main__.py` (`cmd_run`, `_process_pool`), `config.yaml`

**Interfaces:**
- Consumes: Task 1, Task 2.
- Produces: config `scroll_passes: [24, 40, 60]`, `run_deadline_min: 315`, `daily_target: 20`, `sync_target: 0` (0 = enviar todas as novas).

- [ ] **Step 1:** `_process_pool` deixa de parar em `len(picked) >= target`; passa a parar só por `deadline` ou fim das palavras. `target` vira só meta de log.
- [ ] **Step 2:** `cmd_run` repete o pool principal+reserva para cada valor de `scroll_passes` (ajustando `cfg.fetch.max_scrolls`), recomeçando o cursor em 0 a cada passada, enquanto `time.time() < deadline`. Cada passada reaproveita `already`/`known_*`/`rejected` (não reprocessa o que já validou).
- [ ] **Step 3:** `sync_target 0` → `to_sync` = todas as ofertas do SQLite (novas + backlog). Mensagem final informa `validadas/meta` e passadas concluídas.
- [ ] **Step 4:** Verificação: `python -m minerador run --target 3 --deadline 5 --dry-run` termina em ~5 min sem exceção e imprime a passada atual (requer Playwright; se indisponível no ambiente local, registrar que só a verificação em nuvem cobre este passo).
- [ ] **Step 5:** commit.

### Task 4: Garimpo pelos anunciantes validados

**Files:** Modify `minerador/__main__.py`, `minerador/fetch.py` (reusar `verify_many` ou método de página do anunciante); Test: verificação manual no dry-run.

**Interfaces:**
- Produces: `_snowball(m, cfg, conn, known_pages, known_domains, picked, picked_keys, deadline) -> None`: para cada `page_id` em `synced` (ordem de maior `ad_count`), abre a biblioteca do anunciante, agrupa os anúncios por domínio com `build_offers`, e passa os candidatos novos pelo mesmo funil (`evaluate`) já usado em `_process_pool`.

- [ ] **Step 1:** Extrair do `_process_pool` o trecho "candidato → contagem → filtro forte → picked" numa função `_validate_candidate(...) -> bool` usada pelos dois fluxos.
- [ ] **Step 2:** Implementar `_snowball` e chamá-lo após a última passada, enquanto houver tempo.
- [ ] **Step 3:** commit.

### Task 5: Nota via Gemini

**Files:** Create `minerador/nota.py`; Modify `requirements.txt` (`google-genai`), `config.yaml` (`gemini_model`); Test `tests/test_nota.py`

**Interfaces:**
- Produces: `CRITERIOS = ("Dor forte","Promessa desejável","Público comprador","Transformação clara","Valor percebido","Facilidade de compra")`; `parse_notas(raw: str) -> dict[str,int] | None` (JSON com as 6 chaves, inteiros 1–10; qualquer falha → `None`); `media(notas: dict) -> float | None` (média com 1 casa; `None` se faltar critério); `avaliar(oferta_texto: str, api_key: str, model: str) -> dict | None` (chama Gemini com JSON estruturado, 1 retry em 429 com espera de 20 s, `None` em qualquer erro).

- [ ] **Step 1: testes** — `test_parse_notas_ok`, `test_parse_notas_rejects_out_of_range` (11 ou 0 → `None`), `test_parse_notas_rejects_missing_key`, `test_media_needs_all_six`, `test_media_rounds_one_decimal`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. O prompt instrui: avaliar só pelo texto fornecido, notas inteiras 1–10 nos 6 critérios do Julio (descritos com as perguntas originais), responder JSON, e usar `null` quando o texto não permitir avaliar. Texto de entrada = copy do anúncio + página, cortado em 6000 caracteres.
- [ ] **Step 4:** PASS; commit.

### Task 6: Colunas e escrita das notas no Notion

**Files:** Modify `minerador/notion_setup.py`, `minerador/notion_sync.py`; Test `tests/test_merge.py` (parte de props)

**Interfaces:**
- Consumes: Task 5.
- Produces: `notion_setup.ensure_nota_columns(notion, database_id) -> None` (cria as 7 colunas `number` se faltarem, `NOTA MÉDIA` incluída; idempotente); `notion_sync.nota_props(notas: dict | None) -> dict` (props Notion; `{}` se `None`).

- [ ] **Step 1: teste** `test_nota_props_empty_when_none` e `test_nota_props_has_seven_number_props`.
- [ ] **Step 2–4:** implementar; `sync()` chama `ensure_nota_columns` uma vez e inclui `nota_props` na criação/atualização quando a oferta tem notas. Para a coluna `NOTA MÉDIA` ficar visualmente primeira, mover a propriedade no layout da view não é possível via API: documentar no `SETUP-GITHUB.md` que o Julio arrasta a coluna para o início uma vez.
- [ ] **Step 5:** commit.

### Task 7: Merge, dedup entre jobs e workflow paralelo

**Files:** Create `minerador/merge.py`; Modify `.github/workflows/minerador.yml`, `minerador/notion_sync.py`, `minerador/__main__.py`; Test `tests/test_merge.py`

**Interfaces:**
- Produces: `merge.merge_dbs(main_path: Path, job_paths: list[Path]) -> int` (une `synced`, `blocked`, `rejected`, `kv`, `offer_history`, `offers` dos bancos dos jobs no principal; conflito de `offer_key` fica com o `synced_at` mais recente; devolve nº de ofertas novas em `synced`); `python -m minerador merge --jobs-dir DIR` (chama `merge_dbs`, avalia notas das ofertas novas do dia e atualiza as páginas no Notion).

- [ ] **Step 1: testes** — `test_merge_unions_synced`, `test_merge_keeps_latest_synced_at`, `test_merge_unions_rejected_and_blocked`, `test_merge_empty_job_db_ok`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar `merge_dbs` e o subcomando `merge`.
- [ ] **Step 4:** Dedup entre jobs: em `notion_sync.sync`, antes de `pages.create`, consultar o Notion por título igual (`OFERTA` equals) e, se existir, atualizar em vez de criar.
- [ ] **Step 5:** Workflow: job `mine` com `strategy: {fail-fast: false, matrix: {job: [0,1,2,3]}}`, `MINERADOR_JOB=${{ matrix.job }}`, `MINERADOR_JOBS=4`, `MINERADOR_TABS=1`, `MINERADOR_DELAY="3.0,6.5"`, `continue-on-error`, `timeout-minutes: 345`, envia `data/minerador.db` como artifact `db-${{ matrix.job }}` (`if: always()`); job `merge` (`needs: mine`, `if: always()`) baixa os artifacts, roda `merge`, `recalc`, `prune`, comita e envia os logs de rejeição; `GEMINI_API_KEY` e `NOTION_TOKEN` nos envs. Manter `concurrency` e o cron das 06h BRT.
- [ ] **Step 6:** Validar YAML: `python -c "import yaml;yaml.safe_load(open('.github/workflows/minerador.yml'))"`; commit.

### Task 8: Documentação e entrega

**Files:** Modify `CLAUDE.md`, `SETUP-GITHUB.md`

- [ ] **Step 1:** Documentar os 4 jobs, a meta, as passadas, os segredos (`NOTION_TOKEN`, `GEMINI_API_KEY`) e o passo de arrastar `NOTA MÉDIA`.
- [ ] **Step 2:** Rodar `pytest -v` completo → tudo PASS.
- [ ] **Step 3:** `git pull --rebase origin main`; mostrar `git diff --stat`; **pedir autorização ao Julio antes do `git push`**; após o push, disparar a primeira rodada em Actions → Run workflow e acompanhar.

## Self-review

- Cobertura: 4 jobs/fatias (T2, T7), meta e tempo (T3), sem repetidas (já feito + T1, T7 dedup), sem lixo (T1, T2), nota e colunas (T5, T6), merge/isolamento (T7), snowball (T4), docs/push (T8).
- Nomes consistentes: `rejected_sets`, `slice_for_job`, `parse_notas`, `media`, `ensure_nota_columns`, `nota_props`, `merge_dbs`.
- Proporção: spec curta, plano em tasks sem corpos de função.
