"""Heurística: essa oferta parece um infoproduto?"""
from __future__ import annotations

# Gateways de checkout de infoproduto (BR + LATAM + global)
CHECKOUT_HOSTS = {
    "hotmart.com", "pay.hotmart.com", "go.hotmart.com", "hotmart.com.br", "hotm.art",
    "kiwify.com.br", "kiwify.app", "kiwify.com", "pay.kiwify.com.br",
    "ticto.com.br", "checkout.ticto.com.br", "ticto.app", "payment.ticto.com.br",
    "cakto.com.br", "pay.cakto.com.br", "checkout.cakto.com.br",
    "kirvano.com", "pay.kirvano.com", "checkout.kirvano.com",
    "monetizze.com.br", "app.monetizze.com.br", "adm.monetizze.com.br",
    "eduzz.com", "sun.eduzz.com", "chk.eduzz.com", "eduzz.com.br",
    "braip.com", "ev.braip.com", "braip.com.br",
    "perfectpay.com.br", "checkout.perfectpay.com.br", "go.perfectpay.com.br",
    "greenn.com.br", "payt.com.br", "lastlink.com", "hubla.com", "hub.la",
    "pepper.com.br", "digitalmanager.guru", "voomp.com.br", "guru.com.br",
    "clickbank.net", "digistore24.com", "samcart.com",
    "payhip.com", "stan.store",
    "teachable.com", "thinkific.com", "kajabi.com", "hotmart.com",
}

# Checkouts/gateways GENÉRICOS — muito usados por dropship também. NÃO dão "sim"
# sozinhos; só contam se a copy também tiver cara de infoproduto.
GENERIC_CHECKOUT_HOSTS = {
    "yampi.com.br", "pay.yampi.com.br", "checkout.yampi.com.br",
    "mpago.la", "mercadopago.com.br", "mercadopago.com.mx",
    "checkout.stripe.com", "gumroad.com", "buygoods.com",
    "appmax.com.br", "pay.appmax.com.br", "dooki.com.br",
}

# Onde infoprodutores hospedam a página de vendas / VSL
LANDING_HOSTS = {
    "lovable.app", "netlify.app", "vercel.app", "pages.dev", "web.app",
    "firebaseapp.com", "carrd.co", "framer.website", "framer.app", "webflow.io",
    "wixsite.com", "my.canva.site", "notion.site", "super.site", "gitbook.io",
    "github.io", "systeme.io", "clickfunnels.com", "cartpanda.com",
    "builderall.com", "leadlovers.com", "klickpages.com.br", "klicksite.com.br",
    "instapage.com", "unbounce.com", "getresponsesite.com", "gohighlevel.com",
    "convertri.com", "lp.vc",
}

# Copy com cara de infoproduto BARATO (ebook, planilha, template, pack…)
# — SEM termos de curso (Julio não quer curso/mentoria/coaching)
_COPY_HINTS = (
    "acesso imediato", "área de membros", "area de membros", "acesso vitalício",
    "acesso vitalicio", "e-book", "ebook", "vagas limitadas",
    "garantia de 7", "garantia incondicional",
    "apostila", "protocolo",
    "passo a passo", "guia completo", "guia definitivo",
    "receitas", "planilha", "modelos prontos", "template", "templates",
    "acceso inmediato", "descarga", "conteúdo exclusivo", "material completo",
    "quero acesso", "por apenas", "de r$", "por r$", "12x de", "acesso ao",
    "no seu email", "receba no e-mail", "kit ", "combo de",
)

# Palavra no próprio domínio que denuncia infoproduto barato (receitas., planilha., …)
_INFO_DOMAIN_WORDS = (
    "ebook", "e-book", "receita", "receitas", "formula", "fórmula", "protocolo",
    "planilha", "almoco", "almoço", "fitness", "exercicio", "exercício",
    "dieta", "cardapio", "cardápio", "guia", "kit", "apostila",
    "descomplica", "descomplicando", "domine", "segredo", "passoapasso",
    "template", "templates", "planner", "presets", "figurinha", "figurinhas",
)

# CURSO no domínio — REJEIÇÃO DURA (Julio: já passaram DecoKit/eduliv/academy 2x).
# Sem escape por is_cheap_file: domínio assim é curso, ponto.
_COURSE_DOMAIN_HARD = (
    "academy", "academia", "escola", "school", "eduliv", "bootcamp", "escuela",
)
# CURSO mais ambíguo (no domínio ou na copy) — rejeita a NÃO SER que seja
# claramente um arquivo barato (template/pack/ebook/planilha/preset/...).
_COURSE_DOMAIN_WORDS = (
    "coaching", "curso", "cursos", "mentoria", "ensino", "masterclass",
    "treinamento", "formacao", "formação",
)
# Biz-opp / "renda extra" / oportunidade — Julio NÃO quer
_BIZOPP = (
    "renda extra", "renda online", "trabalhe de casa", "trabalhe em casa",
    "trabalhar de casa", "ganhe dinheiro", "ganhar dinheiro", "seja um consultor",
    "seja um revendedor", "seja um afiliado", "seja uma revendedora", "host agency",
    "travel agent", "work from home", "make money online", "gana dinero",
    "ingreso extra", "gana desde casa", "oportunidade de negócio", "oportunidade de negocio",
)
_COURSE_COPY = (
    "mentoria", "imersão", "imersao", "masterclass", "aula ao vivo",
    "aulas ao vivo", "encontros ao vivo", "próxima turma", "proxima turma",
    "matrícula", "matricula", "carga horária", "carga horaria",
    "certificado de conclusão", "certificado de conclusao", "módulos do curso",
    "modulos do curso", "acompanhamento individual", "coaching",
    "grupo de mentoria", "formação completa", "formacao completa", "escola de",
    "curso completo", "curso online", "curso de ", "curso práctico",
    "treinamento completo", "clases en vivo", "método completo", "metodo completo",
)
# Formato de arquivo barato — se tiver isto, NÃO trata como curso
_PRODUCT_FORMAT_HINTS = (
    "template", "templates", "plantilla", "plantillas", "pack de", "pack com",
    "bundle", "preset", "presets", "planilha", "spreadsheet", "ebook", "e-book",
    " pdf", "figurinha", "sticker", "kit de artes", "kit de modelos",
    "modelos editáveis", "printable", "canva", "notion template", "apostila",
    "checklist", "cardápio", "recetario", "arquivo digital", "planner",
)

# Sinais de produto FÍSICO / dropship / nutra — desqualifica
_PHYSICAL_HINTS = (
    "frete grátis", "frete gratis", "frete para todo", "pagamento na entrega",
    "entrega em ", "receba em casa", "envio imediato", "últimas unidades",
    "ultimas unidades", "em estoque", "compre 1 leve", "compre 2 leve",
    "pague na entrega", "rastreio", "código de rastreio", "loja oficial",
    "envío gratis", "pago contra entrega", "unidades disponibles",
    "garantia de fábrica", "nota fiscal", "trocas e devoluções",
    "mau hálito", "mau halito", "bafo", "rugas", "flacidez", "firmeza da pele",
    "clareador", "clareamento dental", "gengiva", "queda de cabelo", "calvície",
    "disfunção", "ereção", "próstata", "hemorroida", "fungo", "unha",
    "spray ", "em gotas", "cápsulas", "capsulas", "gel ", "pomada", "creme ",
    "colágeno", "colageno", "suplemento", "vitamina", "chá ", "emagrecedor",
    # dropship de gadget / vestuário / casa / pet físico
    "capinha", "capinhas", "película", "pelicula", "óculos", "oculos de",
    "relógio", "relogio ", "smartwatch", "fone de ouvido", "caixa de som",
    "camiseta", "blusa", "vestido", "calça", "tênis", "tenis ", "chinelo",
    "sandália", "sandalia", "bolsa ", "mochila", "carteira", "boné", "bone ",
    "caneca", "garrafa", "squeeze", "kit com ", "cerâmica", "ceramica",
    "vaso ", "luminária", "luminaria", "abajur", "tapete", "almofada", "cortina",
    "organizador", "porta-", "utensílio", "utensilio", "panela", "air fryer",
    "airfryer", "brinquedo", "pelúcia", "pelucia", "boneca ", "coleira",
    "comedouro", "bebedouro", "arranhador", "aquário", "aquario", "ração",
    "racao", "tapete higiênico", "cama pet", "produto físico", "produto fisico",
    "cor:", "tamanho:", "voltagem", "bivolt", "110v", "220v", "garantia de 1 ano",
    "parcele em até 12x", "adicionar ao carrinho", "comprar agora",
)


def _host_matches(domain: str, hosts) -> bool:
    if not domain:
        return False
    return any(domain == h or domain.endswith("." + h) for h in hosts)


def is_checkout(domain: str) -> bool:
    return _host_matches(domain, CHECKOUT_HOSTS)


def _domain_smells_info(domain: str) -> bool:
    d = (domain or "").split(".")[0].lower() if domain else ""
    full = (domain or "").lower()
    return any(w in full for w in _INFO_DOMAIN_WORDS) or bool(d) and any(
        w in d for w in _INFO_DOMAIN_WORDS)


# Físico/nutra "forte" — 1 só já derruba no estágio 1 (não vale a pena abrir a página)
_HARD_PHYSICAL = (
    "cápsulas", "capsulas", "colágeno", "colageno", "suplemento", "emagrecedor",
    "spray ", "em gotas", "pomada", "creme ", "clareamento dental", "queda de cabelo",
    "calvície", "disfunção", "ereção", "próstata", "hemorroida",
    "frete grátis", "frete gratis", "pagamento na entrega", "pague na entrega",
    "código de rastreio", "adicionar ao carrinho", "envío gratis", "pago contra entrega",
    "air fryer", "airfryer", "smartwatch", "capinha", "capinhas",
)


def looks_like_infoproduct(offer) -> bool:
    """Estágio 1 (barato, sem abrir página). Afrouxado: só corta o ÓBVIO —
    o filtro forte (salespage.py) abre a página e dá a palavra final.
    Melhor deixar um talvez passar pro estágio 2 do que perder oferta boa
    por causa de 1 palavra numa amostra de copy curta / dinâmica."""
    dom = offer.domain or ""
    text = (offer.sample_copy or "").lower()
    hints = sum(1 for h in _COPY_HINTS if h in text)
    physical = sum(1 for h in _PHYSICAL_HINTS if h in text)
    hard_physical = any(h in text for h in _HARD_PHYSICAL)
    info_dom = _domain_smells_info(dom)
    has_real_copy = len(text.strip()) >= 30 and "{{" not in text
    full_dom = (dom or "").lower()

    # biz-opp / renda extra → fora
    if any(b in text for b in _BIZOPP) or any(b in full_dom for b in
                                              ("rendaextra", "trabalhedecasa", "ganhe")):
        return False

    # curso no domínio (academy/escola/eduliv/bootcamp) → REJEIÇÃO DURA, sem escape
    if any(w in full_dom for w in _COURSE_DOMAIN_HARD):
        return False

    # físico forte (nutra, frete grátis, carrinho, gadget) → fora,
    # a não ser checkout de infoproduto puro. Sinais fracos: 2+ pra derrubar.
    if not _host_matches(dom, CHECKOUT_HOSTS):
        if hard_physical or physical >= 2:
            return False

    # curso mais ambíguo (copy ou domínio) → só passa se for arquivo barato claro
    is_course = (any(w in full_dom for w in _COURSE_DOMAIN_WORDS)
                 or any(h in text for h in _COURSE_COPY))
    is_cheap_file = (any(h in text for h in _PRODUCT_FORMAT_HINTS)
                     or any(w in full_dom for w in
                            ("template", "planner", "presets", "figurinha",
                             "plantilla", "pack")))
    if is_course and not is_cheap_file:
        return False

    # checkout de infoproduto (hotmart/kiwify/ticto/...) = sim
    if _host_matches(dom, CHECKOUT_HOSTS):
        return True

    # daqui pra baixo é candidato pro estágio 2 (abrir a página decide).
    # Critério frouxo: passa se tiver QUALQUER pista, ou se a copy for dinâmica
    # ({{...}}) e não der pra julgar — a página confirma.
    dyn_copy = "{{" in (offer.sample_copy or "")

    if _host_matches(dom, GENERIC_CHECKOUT_HOSTS):
        return hints >= 1 or dyn_copy

    if info_dom:
        return True

    if _host_matches(dom, LANDING_HOSTS):
        return hints >= 1 or dyn_copy or bool((offer.page_name or "").strip())

    if not dom or dom == "(sem link)":
        return False

    # domínio próprio comum
    fmt_in_dom = any(w in full_dom for w in
                     ("template", "planner", "preset", "figurinha", "plantilla",
                      "pack", "ebook", "planilha", "kit", "receita", "cardapio",
                      "apostila", "digital", "artes", "moldes"))
    return hints >= 2 or fmt_in_dom or (dyn_copy and hints >= 1)
