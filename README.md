# Minerador de ofertas low ticket — Biblioteca de Anúncios

Varre a Biblioteca de Anúncios da Meta em **BR + US + ES + MX**, capturando o GraphQL
interno. Agrupa anúncios em **ofertas**, mantém só as que **parecem infoproduto low
ticket** e têm **10–99 anúncios ativos** (contagem verificada abrindo a biblioteca de
cada anunciante), pontua o **calor de 1 a 10**, e joga as N ofertas mais quentes num
banco enxuto do Notion. Não repete oferta já enviada.

## Instalação (uma vez)

```bash
cd "PROJETO MINERADOR"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
```

## Uso

```bash
scripts/run.sh run                       # minera até 20 VALIDADAS -> Notion
scripts/run.sh run --progress            # + escreve data/progress.json ao vivo
scripts/run.sh run --target 3 --dry-run  # teste: 3 ofertas, sem tocar no Notion
scripts/run.sh recalc                    # atualiza contadores + TENDÊNCIA das que já estão no Notion
scripts/run.sh list --top 30             # ver o SQLite
scripts/run.sh sync                      # empurra o SQLite pro Notion (sem minerar)
scripts/run.sh export ofertas.csv
```

### v6 — filtro forte + 20 validadas

Cada rodada minera **até fechar 20 ofertas validadas**. "Validada" = o script abriu a
**página de vendas** e confirmou: checkout de infoproduto, preço ≤ `price_ceiling_brl`
(câmbio do dia), 9–99 anúncios ativos, e **não** é e-commerce / curso / produto físico /
biz-opp. Se as `keywords` não fecharem 20, entra o pool `keywords_reserve`. Se a
biblioteca secar, sobe o que tem e reporta `BIBLIOTECA SECA`.

Países: BR PT MX CO PE CL AR ES US. Reciclagem: oferta apagada do Notion, ou parada há
`recycle_days`, volta pro pool (re-minerar atualiza a mesma página, não duplica).

### Automático todo dia (nuvem)

Roda no **GitHub Actions** todo dia às 06:00 (Brasília), sem depender do Mac.
Setup e como acompanhar: **[SETUP-GITHUB.md](SETUP-GITHUB.md)**.

## config.yaml

| Campo | O quê |
|---|---|
| `countries` | ISO-2. `BR PT MX CO PE CL AR ES US`. Roteamento por idioma em `minerador/lang.py`. |
| `keywords` / `keywords_reserve` | principais + reserva (só entra se não fechar 20). Janelas de `keyword_window`. |
| `daily_target` / `sync_target` | quantas validadas minerar / quantas mandar pro Notion (20). |
| `min_ads` / `max_ads` | 9 e 99 — contagem **real** (verificada abrindo a biblioteca). |
| `price_ceiling_brl` | teto de low ticket; o filtro forte lê o preço na página e converte (`minerador/fx.py`). |
| `recycle_days` | oferta parada há N dias volta pro pool. |
| `infoproduct_only` | filtro estágio 1 (domínio/copy). O estágio 2 (`minerador/salespage.py`) abre a página. |

### Overrides por env (usados no job de nuvem)
`MINERADOR_TABS`, `MINERADOR_DELAY` (`"3.0,6.5"`), `MINERADOR_HEADLESS`.

## Notion — 🟧 OFERTAS LOW

<https://app.notion.com/p/45235b1644114ef492929061c6163647> · colunas: **OFERTA · PAÍS ·
PALAVRA-CHAVE · NÚMERO DE ANÚNCIOS · DIAS ATIVOS · LINK PÁGINA DE VENDAS · BIBLIOTECA ·
ÚLTIMA CHECAGEM · VARIAÇÃO ONTEM · HISTÓRICO · TENDÊNCIA · MINERADO EM**.

A integração `NOTION_TOKEN` já está conectada ao banco. `recalc` cria a coluna
**TENDÊNCIA** (🚀 ESCALANDO / 📈 SUBINDO / ➡️ ESTÁVEL / 📉 CAINDO / 💀 MORRENDO) sozinho.

## Calor (1–10, uso interno)

`dias ativo` (0.40) · `nº de anúncios` (0.30) · `cópias do criativo` (0.20) ·
`recência` (0.10). Só ordena quais ofertas sobem primeiro; não é coluna no Notion.

## Quando quebrar

`run` volta `0 anúncios` + `data/raw/*__EMPTY.json` → a Meta mudou o GraphQL, manda o
arquivo pro Claude. Rate-limit → `fetch.proxy` no config + aumenta `delay_seconds`.
