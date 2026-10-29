"""Nota 1-10 da força comercial da oferta, dada pelo Gemini (plano grátis).
Nunca inventa: erro, limite, texto vazio ou resposta fora do formato -> None (colunas vazias)."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

CRITERIOS = ("Dor forte", "Promessa desejável", "Público comprador",
             "Transformação clara", "Valor percebido", "Facilidade de compra")

_PROMPT = """Você avalia a força comercial de uma oferta de infoproduto low ticket brasileiro.
Use SOMENTE o texto abaixo (copy do anúncio e página de vendas). Não invente nada.
Dê nota INTEIRA de 1 a 10 em cada critério. Se o texto não permite avaliar um critério, use null.

Critérios:
- "Dor forte": resolve um problema urgente, frequente ou emocionalmente relevante?
- "Promessa desejável": entrega um resultado específico que o público realmente quer?
- "Público comprador": atende pessoas com disposição para pagar pela solução?
- "Transformação clara": existe um antes e depois facilmente compreensível?
- "Valor percebido": a solução parece valer mais do que seu preço?
- "Facilidade de compra": a oferta é simples de entender e desperta desejo imediato?

Responda APENAS um JSON com exatamente essas 6 chaves.

TEXTO:
"""

_MAX_CHARS = 6000


class RateLimited(Exception):
    pass


def parse_notas(raw: str):
    """JSON (com ou sem ```) -> {critério: int 1-10} ou None se qualquer coisa estiver errada."""
    try:
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
        data = json.loads(txt)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    out = {}
    for c in CRITERIOS:
        v = data.get(c)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or not 1 <= v <= 10:
            return None
        out[c] = int(v)
    return out


def media(notas):
    """Média com 1 casa, só se as 6 notas existem."""
    if not notas or any(c not in notas or notas[c] is None for c in CRITERIOS):
        return None
    return round(sum(notas[c] for c in CRITERIOS) / len(CRITERIOS) + 1e-9, 1)


def _http_post(url: str, body: dict, key: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited() from e
        raise


def avaliar(texto: str, api_key: str, model: str, post=_http_post, wait: float = 20.0):
    """Chama o Gemini. 1 retry em 429. Qualquer falha -> None."""
    if not api_key or not (texto or "").strip():
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": _PROMPT + texto.strip()[:_MAX_CHARS]}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    for attempt in (0, 1):
        try:
            resp = post(url, body, api_key)
            parts = resp["candidates"][0]["content"]["parts"]
            return parse_notas("".join(p.get("text", "") for p in parts))
        except RateLimited:
            if attempt == 0:
                time.sleep(wait)
        except Exception:
            return None
    return None
