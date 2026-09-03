"""Câmbio pra BRL. Usado pelo filtro forte pra comparar o preço da página
de vendas com o teto de low ticket (config.price_ceiling_brl).

Busca as taxas 1x por dia (open.er-api.com, grátis, sem chave) e guarda no
SQLite (kv). Se a rede falhar, cai numa tabela fixa aproximada — melhor um
número defasado do que travar a rodada.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

# quantos BRL vale 1 unidade da moeda (fallback ~set/2026)
_FALLBACK = {
    "BRL": 1.0, "USD": 5.4, "EUR": 6.0, "MXN": 0.30, "COP": 0.0013,
    "PEN": 1.45, "CLP": 0.0057, "ARS": 0.0037, "GBP": 7.0,
}
_API = "https://open.er-api.com/v6/latest/BRL"


def _fetch_rates() -> dict | None:
    try:
        with urllib.request.urlopen(_API, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        rates = data.get("rates") or {}
        # a API dá BRL->X; queremos X->BRL
        out = {"BRL": 1.0}
        for cur, v in rates.items():
            if isinstance(v, (int, float)) and v > 0:
                out[cur] = 1.0 / v
        return out if len(out) > 5 else None
    except Exception:
        return None


def rates(conn=None) -> dict:
    """Taxas X->BRL. Cacheia por dia no kv se `conn` for dado."""
    today = datetime.now(timezone.utc).date().isoformat()
    if conn is not None:
        try:
            from . import store
            cached = store.kv_get(conn, "fx_rates")
            cached_day = store.kv_get(conn, "fx_rates_day")
            if cached and cached_day == today:
                return {**_FALLBACK, **json.loads(cached)}
        except Exception:
            pass
    live = _fetch_rates()
    if live and conn is not None:
        try:
            from . import store
            store.kv_set(conn, "fx_rates", json.dumps(live))
            store.kv_set(conn, "fx_rates_day", today)
        except Exception:
            pass
    return {**_FALLBACK, **(live or {})}


def to_brl(amount: float, currency: str, table: dict | None = None) -> float:
    t = table or _FALLBACK
    return amount * t.get(currency.upper(), _FALLBACK.get(currency.upper(), 1.0))
