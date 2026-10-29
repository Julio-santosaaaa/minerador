# Automação na nuvem — GitHub Actions

Roda o minerador **todo dia às 06:00 (horário de Brasília)** sem depender do seu Mac.
Minera até 20 validadas → sobe pro Notion → roda o `recalc` (TENDÊNCIA) → guarda o
estado (`data/minerador.db`) commitando de volta no repo.

## Passo a passo (uma vez, ~10 min)

### 1. Criar o repositório privado

1. github.com → **New repository**
2. Nome: `minerador` (o que quiser) · **Private** · **não** marque "Add a README"
3. Create repository

### 2. Mandar o código pra lá

Copie os comandos que o GitHub mostra na tela do repo novo, ou:

```bash
cd "PROJETO MINERADOR"
git remote add origin https://github.com/SEU_USUARIO/minerador.git
git branch -M main
git push -u origin main
```

(Se pedir senha: use um **Personal Access Token** em vez da senha —
github.com → Settings → Developer settings → Personal access tokens → Fine-grained →
dá acesso `Contents: Read and write` a esse repo.)

### 3. Colar o token do Notion como secret

1. No repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Name: `NOTION_TOKEN`
3. Secret: o valor que está no seu arquivo `.env` local (a linha `NOTION_TOKEN=...`)
4. Add secret

### 4. Ligar

1. No repo → aba **Actions** → se pedir, **I understand my workflows, go ahead and enable them**
2. Clique em **minerador** (menu à esquerda) → **Run workflow** → **Run workflow**
   (pra testar agora, sem esperar as 6h)
3. Acompanhe o run. Se ficar verde, tá pronto — roda sozinho todo dia.

## Como acompanhar

- **Aba Actions** → cada dia tem um run. Verde = ok. Clique pra ver o log.
- **Rejeições**: cada run guarda os `reject_*.txt` em **Artifacts** (no fim da página do run), 14 dias.
- **Notion**: o banco 🟧 OFERTAS LOW é atualizado direto.

## Rodar na mão (quando quiser, do Mac)

Continua funcionando igual: `scripts/run.sh run` e `scripts/run.sh recalc`.
O `git pull` antes de rodar na mão evita conflito com o estado que a nuvem commitou.

## Limitações (já conversado)

- IP de datacenter → a Meta bloqueia mais fácil. ~30–60% das rodadas vêm com menos
  ofertas. Não é permanente, recupera na semana. Config já está em ritmo lento
  (`MINERADOR_TABS=1`, delays 3–6,5s) pra reduzir isso.
- GitHub Actions grátis: 2000 min/mês em repo privado. Rodada lenta ~90 min/dia
  ≈ 2700 min/mês → pode passar ~US$1–3/mês. Pra ficar 100% grátis: repo **público**
  (código exposto) ou rodar dia sim dia não.
- Pra chegar perto de 20/dia de verdade: proxy residencial (`fetch.proxy` no config)
  ou rodar 2x/dia.
