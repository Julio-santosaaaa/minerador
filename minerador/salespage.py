"""Filtro FORTE — abre a página de vendas do candidato e decide se é
infoproduto low ticket de verdade.

Regra (combinada com o Julio):
  - acha preço  → só passa se, convertido pra BRL, for <= price_ceiling_brl
  - sem preço   → passa só se tiver (checkout de infoproduto OU entrega digital
                  explícita) E algum sinal de low ticket
  - REJEITA sempre: plataforma de e-commerce no HTML, frete/estoque/variação,
                    página de curso (área de aluno / módulos em vídeo)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from . import fx
from .infoproduct import CHECKOUT_HOSTS, GENERIC_CHECKOUT_HOSTS, _host_matches

_ECOMMERCE_MARKERS = (
    "cdn.shopify.com", "shopify.theme", "myshopify.com", "x-shopify-stage",
    "tiendanube", "nuvemshop", "d2r9epyceweg5n", "lojaintegrada", "cdn.awsli",
    "woocommerce", "wp-content/plugins/woocommerce", "vtex.com.br", "vteximg",
    "magento", "prestashop", "wixstores", "wix stores", "add-to-cart",
    "adicionar ao carrinho", "añadir al carrito", "anadir al carrito",
    "data-product-id", "product-variant", "adicionar à sacola", "meu carrinho",
    "continuar comprando", "calcular frete", "opções de frete", "cep de entrega",
)
_DIGITAL_DELIVERY = (
    "acesso imediato", "área de membros", "area de membros", "acesso vitalício",
    "acesso vitalicio", "no seu e-mail", "no seu email", "enviado por e-mail",
    "download imediato", "baixe agora", "arquivo digital", "acesso ao conteúdo",
    "acceso inmediato", "descarga inmediata", "descarga digital", "instant access",
    "instant download", "google drive", "área do aluno", "area do aluno",
    "liberado na hora", "receba agora",
)
_LOWTICKET_SIGNALS = (
    "por apenas", "de r$", "por r$", "12x de", "à vista", "no pix", "oferta",
    "hoje por", "por solo", "solo $", "only $", "one time payment", "pagamento único",
    "pago único", "super desconto", "promoção", "de r$ ", "menos de r$",
)
_COURSE_PAGE = (
    "área do aluno", "area do aluno", "módulos do curso", "modulos do curso",
    "aulas gravadas", "aulas ao vivo", "carga horária", "carga horaria",
    "certificado de conclusão", "certificado de conclusao", "próxima turma",
    "proxima turma", "matrícula", "matricula", "encontros ao vivo",
    "mentoria em grupo", "curso completo", "acompanhamento individual", "+ de 100 aulas",
)
_PHYSICAL_PAGE = (
    "frete grátis", "frete gratis", "calcular frete", "prazo de entrega",
    "unidades em estoque", "últimas unidades", "cor:", "tamanho:", "voltagem",
    "receba em casa", "código de rastreio", "codigo de rastreio", "envío gratis",
    "pago contra entrega", "trocas e devoluções", "nota fiscal",
)

_PRICE_RE = re.compile(
    r"(R\$|US\$|U\$|\$|€|MXN|COP|ARS|CLP|PEN|S/)\s*"
    r"(\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)",
    re.I)
_INSTALLMENT_HINT = ("x de", "x sem juros", "x s/ juros", "parcel", "vezes de", "cuotas")
_SYM_CUR = {"r$": "BRL", "us$": "USD", "u$": "USD", "€": "EUR",
            "mxn": "MXN", "cop": "COP", "ars": "ARS", "clp": "CLP",
            "pen": "PEN", "s/": "PEN"}
_BARE_DOLLAR_BY_COUNTRY = {
    "MX": "MXN", "CO": "COP", "AR": "ARS", "CL": "CLP", "PE": "PEN",
    "ES": "EUR", "PT": "EUR", "BR": "BRL", "US": "USD",
}


@dataclass
class Verdict:
    ok: bool
    reason: str
    price_brl: float | None = None
    checkout_host: str = ""
    detail: str = ""          # o que exatamente disparou (marcador, contexto do preço...)


def _host(url: str) -> str:
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def _to_float(num: str) -> float | None:
    s = num.replace(" ", "")
    if "," in s and "." in s:            # 1.997,00  -> 1997.00
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                        # 97,00 / 9,90 -> 97.00 / 9.90
        s = s.replace(",", ".")
    else:                                 # 1.997 -> 1997 (milhar) ; 47 -> 47
        if s.count(".") == 1 and len(s.split(".")[1]) == 3:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_prices(text: str, country: str) -> list[tuple[float, str]]:
    out = []
    low = text.lower()
    for m in _PRICE_RE.finditer(text):
        sym = m.group(1).lower()
        val = _to_float(m.group(2))
        if val is None or not (1 <= val <= 100000):
            continue
        ctx = low[max(0, m.start() - 18):m.start()]
        if any(h in ctx for h in _INSTALLMENT_HINT):
            continue                      # "12x de R$ 97" não é o preço da oferta
        cur = _SYM_CUR.get(sym) or ""
        if sym == "$" or not cur:
            cur = _BARE_DOLLAR_BY_COUNTRY.get(country, "USD")
        out.append((val, cur))
    return out


def _checkout_in_html(html: str) -> str:
    for h in CHECKOUT_HOSTS:
        if h in html:
            return h
    return ""


def evaluate(offer, page_data: dict, cfg, conn=None) -> Verdict:
    html = (page_data.get("html") or "").lower()
    text = page_data.get("text") or ""
    ltext = text.lower()
    final_url = page_data.get("final_url") or ""
    country = offer.countries[0] if getattr(offer, "countries", None) else "BR"

    ec_hits = [mk for mk in _ECOMMERCE_MARKERS if mk in html]
    if ec_hits:
        return Verdict(False, "loja / e-commerce (plataforma detectada na página)",
                       detail="marcadores: " + ", ".join(ec_hits[:6]))
    course_hits = [h for h in _COURSE_PAGE if h in ltext]
    if len(course_hits) >= 2:
        return Verdict(False, "página de curso (área de aluno / módulos)",
                       detail="termos: " + ", ".join(course_hits[:6]))
    phys_hits = [h for h in _PHYSICAL_PAGE if h in ltext]
    if len(phys_hits) >= 2:
        return Verdict(False, "produto físico (frete / estoque / variação)",
                       detail="termos: " + ", ".join(phys_hits[:6]))

    checkout = ""
    if _host_matches(_host(final_url), CHECKOUT_HOSTS):
        checkout = _host(final_url)
    if not checkout:
        checkout = _checkout_in_html(html)
    generic_checkout = (_host_matches(_host(final_url), GENERIC_CHECKOUT_HOSTS)
                        or any(g in html for g in GENERIC_CHECKOUT_HOSTS))

    prices = parse_prices(text, country)
    table = fx.rates(conn) if conn is not None else None
    brls = [fx.to_brl(v, c, table) for v, c in prices]
    min_brl = min(brls) if brls else None

    digital = any(h in ltext for h in _DIGITAL_DELIVERY)
    lowticket = any(h in ltext for h in _LOWTICKET_SIGNALS)

    prices_dbg = "preços vistos: " + ", ".join(
        f"{v:.2f} {c}" for v, c in prices[:8]) if prices else "nenhum preço no texto"

    if min_brl is not None:
        if min_brl <= cfg.price_ceiling_brl + 0.01:
            return Verdict(True, f"R$ {min_brl:.0f}", price_brl=round(min_brl, 2),
                           checkout_host=checkout, detail=prices_dbg)
        return Verdict(False, f"preço R$ {min_brl:.0f} acima do teto "
                              f"(R$ {cfg.price_ceiling_brl:.0f})",
                       price_brl=round(min_brl, 2), checkout_host=checkout,
                       detail=prices_dbg)

    # sem preço na página
    if (checkout or digital) and lowticket:
        return Verdict(True, "sem preço, mas checkout/entrega digital + sinal low ticket",
                       checkout_host=checkout,
                       detail=f"checkout={checkout or '-'} digital={digital} lowticket={lowticket}")
    return Verdict(False, "sem preço e sem sinal suficiente de infoproduto low ticket",
                   checkout_host=checkout,
                   detail=f"{prices_dbg} · checkout={checkout or '-'} digital={digital} "
                          f"lowticket={lowticket}")
