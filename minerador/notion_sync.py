from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from . import store
from .config import Config
from .models import Offer

_TZ_BR = timezone(timedelta(hours=-3))

# Colunas do banco no Notion — nomes EXATOS (ver notion_setup.py)
P_TITLE = "OFERTA"
P_LIBRARY = "BIBLIOTECA"
P_DAYS = "DIAS ATIVOS"
P_LINK = "LINK PÁGINA DE VENDAS"
P_ADS = "NÚMERO DE ANÚNCIOS"
P_KEYWORDS = "PALAVRA-CHAVE"
P_COUNTRIES = "PAÍS"
P_MINED = "MINERADO EM"


def _title(offer: Offer) -> str:
    base = f"{offer.page_name} — {offer.domain}" if offer.domain else offer.page_name
    return base.upper()[:1900]


def _props(offer: Offer) -> dict:
    return {
        P_TITLE: {"title": [{"type": "text", "text": {"content": _title(offer)}}]},
        P_LIBRARY: {"url": offer.library_url()},
        P_DAYS: {"number": offer.days_active_max},
        P_LINK: {"url": offer.link_url or None},
        P_ADS: {"number": offer.ad_count},
        P_KEYWORDS: {"multi_select": [{"name": k.replace(",", "")[:90]}
                                      for k in offer.keywords[:10]]},
        P_COUNTRIES: {"multi_select": [{"name": c[:90]} for c in offer.countries[:15]]},
    }


def _create_props(offer: Offer) -> dict:
    """Props na CRIAÇÃO: inclui MINERADO EM = hoje. A view do Notion ordena por
    essa data (asc) → cada rodada nova entra ABAIXO da anterior (pedido do Julio)."""
    p = _props(offer)
    p[P_MINED] = {"date": {"start": datetime.now(_TZ_BR).date().isoformat()}}
    return p


def sync(conn, offers_scored, cfg: Config) -> dict:
    if not cfg.notion_token:
        raise RuntimeError("NOTION_TOKEN vazio no .env")
    if not cfg.notion_database_id:
        raise RuntimeError("notion.database_id vazio no config.yaml")
    try:
        from notion_client import Client
        from notion_client.errors import APIResponseError
    except ImportError as e:
        raise RuntimeError("notion-client não instalado (pip install -r requirements.txt)") from e

    notion = Client(auth=cfg.notion_token)
    created = updated = failed = 0
    synced_ok = []

    for offer, _heat, _level in offers_scored:
        page_id = store.get_notion_page_id(conn, offer.key)
        try:
            if page_id:
                notion.pages.update(page_id=page_id, properties=_props(offer))
                updated += 1
                synced_ok.append((offer.key, page_id))
            else:
                res = notion.pages.create(
                    parent={"database_id": cfg.notion_database_id},
                    properties=_create_props(offer),
                )
                created += 1
                synced_ok.append((offer.key, res["id"]))
        except APIResponseError as e:
            failed += 1
            print(f"  ! Notion falhou em {offer.key}: {e}")
            if page_id and "Could not find" in str(e):
                store.set_notion_page_id(conn, offer.key, None)
        time.sleep(0.34)  # ~3 req/s

    # tudo que entrou no Notion sai de 'offers' e fica só em 'synced'
    for key, pid in synced_ok:
        store.archive_offer(conn, key, pid)

    return {"created": created, "updated": updated, "failed": failed}
