from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from .models import Ad

_DOMAIN_STRIP = re.compile(r"^(www|m|l|lm)\.", re.I)
_FB_HOSTS = {"facebook.com", "fb.me", "fb.com", "l.facebook.com", "lm.facebook.com",
            "instagram.com", "l.instagram.com"}


def extract_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    # desembrulha o redirect da Meta: l.facebook.com/l.php?u=<url real>
    if host in {"l.facebook.com", "lm.facebook.com", "l.instagram.com"}:
        inner = parse_qs(parsed.query).get("u", [""])[0]
        if inner:
            return extract_domain(unquote(inner))
    host = _DOMAIN_STRIP.sub("", host)
    if host in _FB_HOSTS or not host:
        return ""
    return host


def _int(v):
    try:
        if v is None or v == "":
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _first(*vals) -> str:
    for v in vals:
        if v:
            return str(v)
    return ""


def iter_ad_nodes(obj):
    """Walk any decoded GraphQL JSON and yield every ad-like dict (deduped by id)."""
    stack = [obj]
    seen = set()
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if "ad_archive_id" in cur and isinstance(cur.get("snapshot"), dict):
                aid = str(cur.get("ad_archive_id") or "")
                if aid and aid not in seen:
                    seen.add(aid)
                    yield cur
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)


def _media_from_snapshot(snap: dict) -> str:
    for vid in snap.get("videos") or []:
        if isinstance(vid, dict):
            u = _first(vid.get("video_preview_image_url"), vid.get("video_hd_url"),
                       vid.get("video_sd_url"))
            if u:
                return u
    for img in snap.get("images") or []:
        if isinstance(img, dict):
            u = _first(img.get("original_image_url"), img.get("resized_image_url"))
            if u:
                return u
    for card in snap.get("cards") or []:
        if isinstance(card, dict):
            u = _first(card.get("video_preview_image_url"), card.get("original_image_url"),
                       card.get("resized_image_url"))
            if u:
                return u
    return ""


def _cards(snap: dict) -> list:
    return [c for c in (snap.get("cards") or []) if isinstance(c, dict)]


_BAD_LINK_HINT = ("politica", "policy", "privac", "termos", "terms", "lgpd", "/ajuda")


def _pick_extra_link(extra_links) -> str:
    for u in extra_links or []:
        if isinstance(u, str) and u.startswith("http") and not any(b in u.lower() for b in _BAD_LINK_HINT):
            return u
    return ""


def parse_ad(node: dict, keyword: str, country: str = "") -> Ad | None:
    aid = str(node.get("ad_archive_id") or "").strip()
    if not aid:
        return None
    snap = node.get("snapshot") or {}
    cards = _cards(snap)

    body = snap.get("body")
    if isinstance(body, dict):
        body_text = body.get("text") or ""
    elif isinstance(body, str):
        body_text = body
    else:
        body_text = ""
    if not body_text and cards:
        body_text = _first(*[c.get("body") for c in cards])

    link_url = _first(snap.get("link_url"), *[c.get("link_url") for c in cards])
    caption = _first(snap.get("caption"), *[c.get("caption") for c in cards])
    title = _first(snap.get("title"), *[c.get("title") for c in cards])
    if not extract_domain(link_url):   # lead-form / fb.me / sem link -> tenta os extra_links
        alt = _pick_extra_link(snap.get("extra_links"))
        if alt:
            link_url = alt

    plats = (node.get("publisher_platform") or node.get("publisher_platforms")
             or snap.get("publisher_platform") or [])
    if isinstance(plats, str):
        plats = [plats]
    plats = [str(p).replace("_", " ").title().replace(" ", "_") for p in plats if p]

    cats = snap.get("page_categories") or node.get("page_categories") or []
    if isinstance(cats, dict):
        cats = list(cats.values())
    cats = [str(c) for c in cats if c]

    domain = extract_domain(link_url) or extract_domain(caption)

    return Ad(
        ad_archive_id=aid,
        page_id=str(node.get("page_id") or snap.get("page_id") or "").strip(),
        page_name=str(node.get("page_name") or snap.get("page_name")
                      or snap.get("current_page_name") or "").strip(),
        page_categories=cats,
        body_text=body_text.strip(),
        title=title.strip(),
        link_url=link_url.strip(),
        caption=caption.strip(),
        domain=domain,
        cta_text=str(snap.get("cta_text") or "").strip(),
        cta_type=str(snap.get("cta_type") or "").strip(),
        start_date=_int(node.get("start_date") or node.get("ad_delivery_start_time")),
        end_date=_int(node.get("end_date") or node.get("ad_delivery_stop_time")),
        total_active_time=_int(node.get("total_active_time")),
        is_active=bool(node.get("is_active", True)),
        publisher_platform=plats,
        collation_count=_int(node.get("collation_count")) or 1,
        page_like_count=_int(snap.get("page_like_count")) or 0,
        media_url=_media_from_snapshot(snap),
        keyword=keyword,
        country=country,
    )


def parse_nodes(nodes, keyword: str, country: str = "") -> list:
    out, seen = [], set()
    for n in nodes:
        ad = parse_ad(n, keyword, country)
        if ad and ad.ad_archive_id not in seen:
            seen.add(ad.ad_archive_id)
            out.append(ad)
    return out
