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

### Automático todo dia (Mac ligado)

```bash
MINERADOR_HOUR=8 scripts/install-cron.sh          # LaunchAgent diário 08:30
scripts/install-cron.sh --uninstall               # remove
launchctl kickstart -k gui/$(id -u)/com.julio.minerador   # rodar agora
tail -f data/cron.log
```
Roda no horário **se o Mac estiver ligado e acordado**. Log em `data/cron.log`.

## config.yaml

| Campo | O quê |
|---|---|
| `countries` | ISO-2. Padrão `BR US ES MX`. |
| `keywords` | lista única (PT+ES+EN). As rodadas **giram** a lista em janelas de `keyword_window`. |
| `daily_target` | quantas ofertas **novas** cada rodada busca (padrão 20). |
| `keyword_window` | palavras-chave por janela; a rodada roda janela após janela até bater o alvo. |
| `min_ads` / `max_ads` | 10 e 99 — contagem **real** (verificada). |
| `infoproduct_only` | filtro de infoproduto (checkout Hotmart/Kiwify/…, landing lovable/netlify/…, ou copy/domínio com cara de curso; corta dropship/nutra). |
| `verify_pages` | abre `view_all_page_id` de cada candidato pra contar os ativos de verdade. |

## Notion — 🟧 OFERTAS LOW

<https://app.notion.com/p/45235b1644114ef492929061c6163647> · colunas: **OFERTA · PAÍS ·
PALAVRA-CHAVE · NÍVEL · CALOR · NÚMERO DE ANÚNCIOS · DIAS ATIVOS · CÓPIAS DO CRIATIVO ·
LINK PÁGINA DE VENDAS · BIBLIOTECA**.

⚠️ **Pra o script escrever sozinho**: abrir o banco no Notion → `•••` → **Conexões** →
adicionar a integração do `NOTION_TOKEN`. Sem isso, a rodada salva no SQLite e você roda
`scripts/run.sh sync` depois de conectar.

## Calor (1–10)

`dias ativo` (0.40) · `nº de anúncios` (0.30) · `cópias do criativo` (0.20) ·
`recência` (0.10). Reescalado pra 1–10. 1 anúncio só leva penalidade.

## Quando quebrar

`run` volta `0 anúncios` + `data/raw/*__EMPTY.json` → a Meta mudou o GraphQL, manda o
arquivo pro Claude. Rate-limit → `fetch.proxy` no config + aumenta `delay_seconds`.
