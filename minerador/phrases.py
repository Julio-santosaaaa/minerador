"""Frases-chave tiradas da copy de ofertas boas — viram novas buscas (ofertas parecidas)."""
from __future__ import annotations

import re

_SPLIT = re.compile(r"[.!?\n:|•–—]+")
_CLEAN = re.compile(r"[^\wÀ-ÿ\s$%,-]", re.UNICODE)


def phrases_from_copies(copies, seen=None, limit: int = 40) -> list:
    """Primeira frase de cada copy (4 a 9 palavras, minúscula, sem emoji/URL/{{}}).
    Dedup e ignora `seen`. Devolve até `limit` frases."""
    seen = set(seen or ())
    out = []
    for text in copies:
        if not text or "{{" in text or "http" in text.lower():
            continue
        first = next((p.strip() for p in _SPLIT.split(text) if p.strip()), "")
        words = _CLEAN.sub(" ", first.lower()).split()[:9]
        if len(words) < 4:
            continue
        phrase = " ".join(words)
        if len(phrase) < 18 or phrase in seen:
            continue
        seen.add(phrase)
        out.append(phrase)
        if len(out) >= limit:
            break
    return out
