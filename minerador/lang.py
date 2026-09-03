"""Mapeia palavra-chave -> países onde faz sentido buscar.

Países do projeto: BR PT MX CO PE CL AR ES US.
  - PT com preço em R$ / Pix        -> só BR (Portugal usa €)
  - PT de formato (ebook, planilha) -> BR + PT
  - ES                              -> MX CO PE CL AR ES
  - EN                              -> US
  - universal (números, canva, notion template, presets...) -> todos
"""
from __future__ import annotations

# PT que só faz sentido no Brasil (moeda/ível de pagamento local)
_PT_BR_ONLY = {
    "de r$ 97 por", "de r$ 47 por", "de r$ 27 por", "de r$ 17 por", "de r$ 197 por",
    "por apenas r$ 10", "por apenas r$ 19,90", "por apenas r$ 27", "por apenas r$ 37",
    "apenas r$ 9,90", "pagamento no pix", "pagamento único", "garantia de 7 dias",
    "de r$ 67 por", "de r$ 37 por", "por apenas r$ 47", "só r$ 19", "12x de",
    "planilha de gastos",
}
# PT de formato / entrega digital — serve BR e Portugal
_PT = {
    "acesso imediato", "acesso vitalício", "planilha", "planilha de", "apostila",
    "cardápio", "receitas", "planner digital", "planner 2026", "pack de", "pack com",
    "template de", "bundle de templates", "modelos editáveis", "arquivo digital",
    "kit de artes", "figurinhas", "kit digital", "artes editáveis", "pack de artes",
    "moldes para", "planilha excel", "dashboard notion", "atividades para imprimir",
    "atividades pedagógicas", "mapas mentais", "caderno digital", "guia prático",
    "cardápio semanal",
}
_ES = {
    "acceso inmediato", "pago único", "acceso de por vida", "por solo $", "por solo $9",
    "recetario", "plantilla de", "plantillas editables", "pack de plantillas",
    "descarga digital", "imprimible", "plantillas canva", "plantillas notion",
    "recetario saludable", "planificador digital", "agenda digital", "kit de plantillas",
    "calcomanías", "pdf editable",
}
_EN = {
    "instant access", "one time payment", "lifetime access", "digital download",
    "printable", "low ticket", "only $7", "only $17", "canva template", "notion template",
    "printable planner", "canva bundle", "notion dashboard", "digital planner",
    "spreadsheet template", "meal plan", "resume template", "$9",
}

_PT_BR = ["BR"]
_PT_ALL = ["BR", "PT"]
_ES_ALL = ["MX", "CO", "PE", "CL", "AR", "ES"]
_EN_ALL = ["US"]


def countries_for(keyword: str, all_countries) -> list:
    k = keyword.strip().lower()
    if k in _PT_BR_ONLY:
        bucket = _PT_BR
    elif k in _PT:
        bucket = _PT_ALL
    elif k in _ES:
        bucket = _ES_ALL
    elif k in _EN:
        bucket = _EN_ALL
    else:
        return list(all_countries)   # universal (ebook, checklist, presets, números...)
    picked = [c for c in bucket if c in all_countries]
    return picked or list(all_countries)
