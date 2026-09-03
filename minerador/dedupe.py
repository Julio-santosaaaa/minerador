from __future__ import annotations

from collections import defaultdict

from .infoproduct import looks_like_infoproduct
from .models import Offer


def _first_nonempty(ads, attr: str) -> str:
    for a in ads:
        v = getattr(a, attr)
        if v:
            return v
    return ""


def _best_copy(ads) -> str:
    real = [a.body_text for a in ads if a.body_text and "{{" not in a.body_text]
    pool = real or [a.body_text for a in ads if a.body_text]
    return max(pool, key=len, default="")[:1800]


def _ignored(domain: str, ignore_domains) -> bool:
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in ignore_domains)


def _count(group) -> int:
    active = [a for a in group if a.is_active] or group
    distinct = len({a.ad_archive_id for a in active})
    return max(distinct, max((a.collation_count for a in active), default=1))


def build_offers(ads, *, ignore_domains=(), infoproduct_only=False) -> list:
    """Ad[] plano -> ofertas dedup por (page_id, domínio). SEM filtro de contagem
    (a contagem exata vem depois, na verificação de página)."""
    groups = defaultdict(list)
    for ad in ads:
        if _ignored(ad.domain, ignore_domains):
            continue
        dom = ad.domain or "(sem link)"
        groups[(ad.page_id or ad.page_name or "?", dom)].append(ad)

    offers = []
    for (pkey, dom), group in groups.items():
        offer = Offer(
            page_id=_first_nonempty(group, "page_id"),
            page_name=_first_nonempty(group, "page_name") or pkey,
            domain=dom,
            link_url=_first_nonempty(group, "link_url"),
            ad_count=_count(group),                       # provisório (amostra)
            days_active_max=max((a.days_active for a in group), default=0),
            collation_total=sum(max(a.collation_count, 1) for a in group),
            platforms=sorted({p for a in group for p in a.publisher_platform}),
            keywords=sorted({a.keyword for a in group if a.keyword}),
            countries=sorted({a.country for a in group if a.country}),
            sample_copy=_best_copy(group),
            media_url=_first_nonempty(group, "media_url"),
            page_categories=sorted({c for a in group for c in a.page_categories}),
            page_like_count=max((a.page_like_count for a in group), default=0),
            started_recently=any(0 < a.days_active <= 14 for a in group),
        )
        if infoproduct_only and not looks_like_infoproduct(offer):
            continue
        offers.append(offer)

    offers.sort(key=lambda o: (o.ad_count, o.days_active_max), reverse=True)
    return offers
