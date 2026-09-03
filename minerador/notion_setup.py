from __future__ import annotations

import os
import sys
import time

from .config import Config

# Schema enxuto — só o que o Julio pediu (+ PAÍS pra separar BR/LATAM/gringa)


def create_database() -> None:
    cfg = Config.load()
    token = cfg.notion_token
    parent = os.getenv("NOTION_PARENT_PAGE_ID", "").strip()
    if not token:
        sys.exit("NOTION_TOKEN vazio no .env")
    try:
        from notion_client import Client
    except ImportError:
        sys.exit("notion-client não instalado (pip install -r requirements.txt)")

    notion = Client(auth=token)
    props = {
        "OFERTA": {"title": {}},
        "PAÍS": {"multi_select": {"options": [
            {"name": "BR", "color": "green"}, {"name": "US", "color": "blue"},
            {"name": "MX", "color": "orange"}]}},
        "PALAVRA-CHAVE": {"multi_select": {"options": []}},
        "NÚMERO DE ANÚNCIOS": {"number": {"format": "number"}},
        "DIAS ATIVOS": {"number": {"format": "number"}},
        "LINK PÁGINA DE VENDAS": {"url": {}},
        "BIBLIOTECA": {"url": {}},
    }
    kwargs = dict(
        title=[{"type": "text", "text": {"content": "Ofertas Low Ticket"}}],
        properties=props,
    )
    if parent:
        kwargs["parent"] = {"type": "page_id", "page_id": parent}
    db = notion.databases.create(**kwargs)
    print("Banco criado:", db.get("url", db["id"]))
    print(f'\nCole no config.yaml:\n  database_id: "{db["id"]}"')


def trim_database() -> None:
    """Remove as colunas CALOR / CÓPIAS DO CRIATIVO / NÍVEL do banco existente."""
    cfg = Config.load()
    if not cfg.notion_token:
        sys.exit("NOTION_TOKEN vazio no .env")
    if not cfg.notion_database_id:
        sys.exit("notion.database_id vazio no config.yaml")
    try:
        from notion_client import Client
    except ImportError:
        sys.exit("notion-client não instalado (pip install -r requirements.txt)")

    notion = Client(auth=cfg.notion_token)
    drop = {"CALOR": None, "CÓPIAS DO CRIATIVO": None, "NÍVEL": None}
    db = notion.databases.retrieve(database_id=cfg.notion_database_id)
    # API nova: o schema fica na data source, não no database
    ds = (db.get("data_sources") or [])
    if ds:
        notion.request(path=f"data_sources/{ds[0]['id']}", method="PATCH",
                       body={"properties": drop})
    else:
        notion.databases.update(database_id=cfg.notion_database_id, properties=drop)
    print("Removidas do Notion: CALOR, CÓPIAS DO CRIATIVO, NÍVEL")


_TREND_OPTIONS = [
    {"name": "🚀 ESCALANDO", "color": "red"},
    {"name": "📈 SUBINDO", "color": "orange"},
    {"name": "➡️ ESTÁVEL", "color": "gray"},
    {"name": "📉 CAINDO", "color": "yellow"},
    {"name": "💀 MORRENDO", "color": "brown"},
    {"name": "🆕 NOVA", "color": "blue"},
]


def ensure_trend_column(notion, database_id: str) -> None:
    """Cria a coluna TENDÊNCIA (select) no banco 🟧 OFERTAS LOW se ainda não existe.
    Idempotente — chamada no início do `recalc`."""
    db = notion.databases.retrieve(database_id=database_id)
    ds = db.get("data_sources") or []
    props = {}
    if ds:
        try:
            full = notion.request(path=f"data_sources/{ds[0]['id']}", method="GET")
            props = full.get("properties", {})
        except Exception:
            props = {}
    else:
        props = db.get("properties", {})
    if "TENDÊNCIA" in props:
        return
    schema = {"TENDÊNCIA": {"select": {"options": _TREND_OPTIONS}}}
    if ds:
        notion.request(path=f"data_sources/{ds[0]['id']}", method="PATCH",
                       body={"properties": schema})
    else:
        notion.databases.update(database_id=database_id, properties=schema)
    print("  + coluna TENDÊNCIA criada no Notion")


def _archive_all(notion, database_id: str) -> int:
    db = notion.databases.retrieve(database_id=database_id)
    ds = (db.get("data_sources") or [])
    ds_id = ds[0]["id"] if ds else None
    path = (f"data_sources/{ds_id}/query" if ds_id
            else f"databases/{database_id}/query")
    n, cursor = 0, None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = notion.request(path=path, method="POST", body=body)
        for pg in resp.get("results", []):
            notion.pages.update(page_id=pg["id"], archived=True)
            n += 1
            time.sleep(0.34)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return n


def clear_database() -> None:
    """Esvazia TUDO (sem excluir bancos nem tabelas): arquiva todas as páginas do
    Notion (banco principal + histórico) e limpa as tabelas de dados do SQLite.
    A próxima rodada começa do zero."""
    cfg = Config.load()
    if not cfg.notion_token or not cfg.notion_database_id:
        sys.exit("NOTION_TOKEN ou notion.database_id ausente")
    try:
        from notion_client import Client
    except ImportError:
        sys.exit("notion-client não instalado (pip install -r requirements.txt)")
    from . import store
    from .config import DB_PATH

    notion = Client(auth=cfg.notion_token)
    n_main = _archive_all(notion, cfg.notion_database_id)
    n_hist = 0
    if cfg.notion_history_database_id:
        try:
            n_hist = _archive_all(notion, cfg.notion_history_database_id)
        except Exception as e:
            print(f"  (histórico: {e})")

    conn = store.connect(DB_PATH)
    for tbl in ("offers", "synced", "offer_history", "ads", "runs"):
        conn.execute(f"DELETE FROM {tbl}")
    store.kv_set(conn, "kw_cursor", 0)
    conn.commit()
    print(f"Notion: {n_main} ofertas + {n_hist} linhas de histórico arquivadas.\n"
          f"SQLite: offers/synced/offer_history/ads/runs zeradas, cursor de keyword resetado.\n"
          f"Bancos e tabelas mantidos. Próxima rodada começa do zero.")
