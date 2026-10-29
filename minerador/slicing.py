"""Fatia as palavras-chave entre os jobs paralelos do Actions."""
from __future__ import annotations

import random


def slice_for_job(keywords: list, job: int, jobs: int) -> list:
    """Embaralha de forma estável (mesma ordem em todos os jobs) e devolve a fatia
    `job` de `jobs`. Fatias são disjuntas e juntas cobrem a lista toda."""
    if jobs <= 1:
        return list(keywords)
    order = list(keywords)
    random.Random(len(order)).shuffle(order)
    return [k for i, k in enumerate(order) if i % jobs == job % jobs]
