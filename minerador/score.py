from __future__ import annotations

import math

_DAYS_CEIL = math.log1p(180)
_CREATIVE_CEIL = math.log1p(25)
_COLLATION_CEIL = math.log1p(100)


def heat(days_active_max: int, creative_count: int, collation_total: int,
         started_recently: bool, weights: dict, min_days_active: int) -> float:
    """Calor de 1 a 10 — 'quão validada/escalando essa oferta parece'."""
    if days_active_max < min_days_active:
        d = 0.0
    else:
        d = min(math.log1p(days_active_max - min_days_active) / _DAYS_CEIL, 1.0)
    if creative_count <= 1:
        d *= 0.55
    c = min(math.log1p(max(creative_count - 1, 0)) / _CREATIVE_CEIL, 1.0)
    k = min(math.log1p(max(collation_total - 1, 0)) / _COLLATION_CEIL, 1.0)
    r = 1.0 if (started_recently and creative_count >= 3) else 0.0

    raw = (weights.get("days_active", 0) * d
           + weights.get("creative_count", 0) * c
           + weights.get("collation", 0) * k
           + weights.get("recency", 0) * r)
    return round(1 + raw * 9, 1)          # 1.0 .. 10.0


def level(score: float) -> str:
    if score >= 7.5:
        return "🔥🔥🔥"
    if score >= 4.5:
        return "🔥🔥"
    return "🔥"
