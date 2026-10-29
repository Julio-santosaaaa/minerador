# Minerador: 20+ ofertas novas por dia, 4 jobs em paralelo e nota por IA (Gemini)

## Intenção
Julio abre o Notion toda manhã e quer **pelo menos 20 ofertas novas e validadas** (nunca vistas, sem repetidas, sem lixo), com uma **nota de força comercial** para triar rápido. Hoje entram só 0 a 6 novas por dia (o resto é reciclagem de ofertas já vistas) porque o pool de ~110 palavras-chave é sempre o mesmo e a rodada encerra com ~1h45 de 290 min.

## Objetivos
1. Rodar **4 jobs em paralelo** no GitHub Actions, cada um com sua fatia das palavras-chave, cada um até o limite de tempo do job.
2. Meta ≥ 20 novas validadas por dia. **Bateu 20, continua até o tempo acabar** e sobe tudo que achar.
3. Zero repetidas: oferta já enviada nunca volta; oferta apagada do Notion é bloqueada para sempre; mesmo anunciante ou domínio base não repete. (Já implementado em 2026-10-29.)
4. Sem lixo: palavras-chave de nicho, filtros de curso/coaching/SaaS, e **memória de páginas rejeitadas** (não reabrir a mesma página ruim todo dia).
5. Nota 1–10 nos 6 critérios do Julio, dada pelo Gemini (plano gratuito), mais NOTA MÉDIA.

## Não objetivos / anti-objetivos
- Não gastar dinheiro: sem API paga. Sem chave Gemini ou com erro/limite, as notas ficam **vazias** (nunca inventadas).
- Não mexer em aba, pausa ou scroll da 1ª passada (modo de hoje, já provado contra bloqueio). Não há teste de parâmetros.
- Não remover nem renomear colunas atuais do Notion.
- Não garantir 20/dia: depende de quanto existe de novo na Biblioteca da Meta.

## Decisões do Julio
- 3 a 5 jobs; escolhido **4**. 6 h de relógio por dia (4 × 6 h = 24 h de máquina).
- Mais de 400 palavras-chave de nicho, mais frases tiradas das ofertas boas.
- Ofertas de qualquer nota sobem ao Notion.
- Notion: colunas atuais intactas + 7 novas: **NOTA MÉDIA** (primeira), **Dor forte, Promessa desejável, Público comprador, Transformação clara, Valor percebido, Facilidade de compra** (cada uma 1 a 10, número).
- Gemini grátis (Julio cria `GEMINI_API_KEY`; guardada como segredo do GitHub).

## Decisões minhas (marcadas como chute do desenho)
- **Fatiamento:** palavras-chave embaralhadas de forma estável e divididas por `índice_do_job % 4`; cursor de rotação por job guardado em `kv` com chave própria (`kw_cursor_<job>`).
- **Passadas por job:** 1ª com 24 scrolls (igual hoje); quando as palavras-chave da fatia acabam, 2ª passada com 40 scrolls e 3ª com 60; depois, garimpo dos outros anúncios dos anunciantes validados (`view_all_page_id`). Cada passada só começa após a anterior.
- **Tempo:** `run_deadline_min` sobe de 290 para 315; `timeout-minutes` do job = 345.
- **Isolamento:** cada job grava num SQLite próprio (cópia do estado do repo) e envia ao Notion só o que ele validou. Um job final (`merge`) baixa os resultados, junta `synced`/`blocked`/`rejected` e faz o commit. Falha ou bloqueio de um job não derruba os outros (`continue-on-error`, `fail-fast: false`).
- **Dedup entre jobs:** como os jobs rodam ao mesmo tempo, antes de criar a página no Notion cada job consulta o Notion (por `page_id`/domínio no título/link) para não duplicar com outro job.
- **Memória de rejeitadas:** tabela `rejected(domain_root, page_id, reason, rejected_at)`; rejeições "duras" (e-commerce, curso, SaaS, físico, preço acima do teto) valem 14 dias; "não abriu a página" vale 2 dias. Candidatos nelas são pulados antes de abrir a página de vendas.
- **Nota:** Gemini `gemini-2.5-flash-lite` (configurável em `config.yaml`), JSON estruturado com as 6 notas; entrada = melhor copy do anúncio + texto da página (cortado em ~6 mil caracteres). Respeita o limite gratuito: pausa entre chamadas, retry em 429, desiste da oferta (notas vazias) em erro. Roda no job `merge` sobre as ofertas novas do dia. Nota média = média das notas preenchidas, só se as 6 vieram.
- **Privacidade:** no plano grátis o Google pode usar o conteúdo enviado para melhorar produtos; aqui são anúncios e páginas públicas.

## Restrições
- Repositório público, Actions grátis, até 20 jobs simultâneos, 256 por matrix (docs do GitHub), job de no máximo 6 h.
- Meta pode bloquear IP de datacenter: o risco por job é igual ao de hoje (1 aba, mesmas pausas); a 2ª e 3ª passadas (mais scrolls) são as de maior risco e vêm por último.
- Notion: ~3 req/s (já respeitado).

## Fica para quem constrói
Lista final de 400+ palavras e roteamento por idioma/país; heurística de frases tiradas das ofertas boas; formato exato do prompt do Gemini; criação das 7 colunas no Notion (`notion_setup`).
