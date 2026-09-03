"""Recálculo diário do tracker de progresso.

Só mexe nas ofertas que JÁ ESTÃO no banco do Notion (🟧 OFERTAS LOW). Pra cada uma:
  1. reabre a Biblioteca de Anúncios da Meta (mesma URL/país da coluna BIBLIOTECA)
  2. relê o nº EXATO de anúncios ativos (campo `count` do GraphQL) + dias ativos
  3. atualiza NÚMERO DE ANÚNCIOS, DIAS ATIVOS, ÚLTIMA CHECAGEM, Δ ONTEM, HISTÓRICO
  4. grava 1 linha no banco 📊 HISTÓRICO ANÚNCIOS (oferta × dia)

NÃO minera palavra-chave nenhuma. NÃO lê o pool do SQLite pra decidir o que checar —
a fonte da verdade é o próprio Notion.

Travas anti-erro: se a contagem vier 0 ou pular mais de 10x (pra cima ou pra baixo)
vs. a última medição, o valor NÃO é escrito no Notion — fica só marcado como
suspeito no SQLite (offer_history.flagged=1) e a coluna HISTÓRICO ganha um "⚠️".
O JSON bruto de cada recálculo é salvo em data/raw/recalc_<data>_<page_id>.json.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from . import store
from .config import Config, DB_PATH, RAW_DIR
from .fetch import Miner, PlaywrightMissing
from .parse import parse_nodes

_TZ_BR = timezone(timedelta(hours=-3))   # America/Sao_Paulo (sem horário de verão desde 2019)

P_ADS = "NÚMERO DE ANÚNCIOS"
P_DAYS = "DIAS ATIVOS"
P_LIBRARY = "BIBLIOTECA"
P_CHECKED = "ÚLTIMA CHECAGEM"
P_DELTA = "VARIAÇÃO ONTEM"
P_HIST = "HISTÓRICO"
P_TREND = "TENDÊNCIA"
P_TITLE = "OFERTA"


def _trend(series: list) -> str:
    """Rótulo de tendência pela variação em ~7 dias (1 ponto por dia no series)."""
    if not series:
        return "🆕 NOVA"
    now = series[-1]
    if now == 0:
        return "💀 MORRENDO"
    if len(series) < 2:
        return "🆕 NOVA"
    past = series[-8] if len(series) >= 8 else series[0]
    if past <= 0:
        return "📈 SUBINDO"
    ch = (now - past) / past
    if ch >= 0.30:
        return "🚀 ESCALANDO"
    if ch >= 0.10:
        return "📈 SUBINDO"
    if ch <= -0.30:
        return "💀 MORRENDO"
    if ch <= -0.10:
        return "📉 CAINDO"
    return "➡️ ESTÁVEL"


def _today() -> str:
    return datetime.now(_TZ_BR).date().isoformat()


def _recount(ads):
    """Mesma lógica do __main__._recount (amostra rolada -> dias ativos)."""
    active = [a for a in ads if a.is_active] or ads
    if not active:
        return 0, 0
    distinct = len({a.ad_archive_id for a in active})
    n = max(distinct, max((a.collation_count for a in active), default=1))
    dmax = max((a.days_active for a in active), default=0)
    return n, dmax


def _lib_target(url: str) -> tuple[str, str]:
    """(page_id, country) a partir da URL da coluna BIBLIOTECA."""
    if not url:
        return "", "BR"
    q = parse_qs(urlparse(url).query)
    pid = (q.get("view_all_page_id") or [""])[0]
    country = (q.get("country") or ["BR"])[0] or "BR"
    return pid, country


def _num(prop) -> float | None:
    return prop.get("number") if isinstance(prop, dict) else None


def _plain_title(prop) -> str:
    try:
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    except Exception:
        return ""


def _spark(series, flagged=False) -> str:
    s = "→".join(str(x) for x in series) if series else ""
    return (("⚠️ " + s) if flagged else s)[:1900]


def _notion_client(cfg: Config):
    if not cfg.notion_token:
        raise RuntimeError("NOTION_TOKEN vazio no .env")
    if not cfg.notion_database_id:
        raise RuntimeError("notion.database_id vazio no config.yaml")
    from notion_client import Client
    return Client(auth=cfg.notion_token)


def _data_source_id(notion, database_id: str) -> str | None:
    try:
        db = notion.databases.retrieve(database_id=database_id)
    except Exception:
        return None
    ds = db.get("data_sources") or []
    return ds[0]["id"] if ds else None


def _query_all(notion, database_id: str, ds_id: str | None = None):
    ds_id = ds_id or _data_source_id(notion, database_id)
    path = (f"data_sources/{ds_id}/query" if ds_id
            else f"databases/{database_id}/query")
    out, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = notion.request(path=path, method="POST", body=body)
        out.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return out


def _history_index(notion, hist_db_id: str, run_date: str, hist_ds_id: str | None) -> dict:
    """{offer_page_id: history_page_id} pras linhas de HOJE — evita duplicar."""
    idx = {}
    if not hist_db_id:
        return idx
    try:
        for pg in _query_all(notion, hist_db_id, hist_ds_id):
            props = pg.get("properties", {})
            d = (props.get("DATA", {}) or {}).get("date") or {}
            if (d.get("start") or "")[:10] != run_date:
                continue
            for rel in (props.get(P_TITLE, {}) or {}).get("relation", []):
                idx[rel["id"]] = pg["id"]
    except Exception as e:
        print(f"  ! não consegui indexar o histórico de hoje: {e}")
    return idx


def cmd_reconcile(args) -> None:
    """Julio apaga ofertas na mão no Notion. Isto tira essas do 'synced' do SQLite
    pra que a próxima rodada possa re-avaliar / backfill até as 20."""
    cfg = Config.load()
    notion = _notion_client(cfg)
    pages = _query_all(notion, cfg.notion_database_id)
    live = {p["id"] for p in pages}
    live |= {p["id"].replace("-", "") for p in pages}
    conn = store.connect(DB_PATH)
    gone = [r["offer_key"] for r in store.all_synced(conn)
            if (r["notion_page_id"] or "").replace("-", "") not in live]
    n = store.forget_synced(conn, gone)
    print(f"Notion tem {len(pages)} ofertas · {n} removidas do 'synced' "
          f"(apagadas por você no Notion → liberadas pra re-minerar).")


def cmd_recalc(args) -> None:
    cfg = Config.load()
    run_date = _today()
    scrolls = getattr(args, "scrolls", None) or cfg.fetch.recalc_scrolls
    cfg.fetch.verify_scrolls = scrolls

    notion = _notion_client(cfg)
    try:
        from .notion_setup import ensure_trend_column
        ensure_trend_column(notion, cfg.notion_database_id)
    except Exception as e:
        print(f"  (não consegui garantir a coluna TENDÊNCIA: {e})")
    pages = _query_all(notion, cfg.notion_database_id)
    if not pages:
        print("Banco do Notion vazio — nada pra recalcular.")
        return
    print(f"Recálculo {run_date} — {len(pages)} ofertas no Notion · scrolls={scrolls}")

    hist_db = cfg.notion_history_database_id
    hist_today = {}   # snapshots no Notion desligados (Julio) — ver write_snapshots

    conn = store.connect(DB_PATH)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ok = flagged = errors = 0

    try:
        with Miner(cfg, RAW_DIR) as m:
            for pg in pages:
                props = pg.get("properties", {})
                title = _plain_title(props.get(P_TITLE, {})) or pg["id"][:8]
                lib = (props.get(P_LIBRARY, {}) or {}).get("url") or ""
                page_id, country = _lib_target(lib)
                prev = _num(props.get(P_ADS, {}))
                prev_days = _num(props.get(P_DAYS, {}))
                key = pg["id"]

                if not page_id:
                    print(f"  ? {title[:34]:34} sem page_id na BIBLIOTECA — pulei")
                    errors += 1
                    continue

                try:
                    nodes = m.verify_page(page_id, country)
                except Exception as e:
                    print(f"  ! {title[:34]:34} falha ao abrir ({e})")
                    errors += 1
                    continue

                ads = parse_nodes(nodes, "", country)
                n, dmax = _recount(ads)
                exact = getattr(m, "last_result_count", 0)
                ad_count = exact or n
                days = dmax or int(prev_days or 0)

                # salva o JSON bruto pra auditoria
                try:
                    (RAW_DIR / f"recalc_{run_date}_{page_id}.json").write_text(
                        json.dumps(nodes[:60], ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass

                base = prev if prev not in (None, 0) else store.last_valid_count(conn, key)
                is_flag = (ad_count == 0) or (
                    base not in (None, 0)
                    and (ad_count > base * 10 or base > ad_count * 10))
                delta = (ad_count - int(base)) if base not in (None, 0) and not is_flag else None

                store.record_history(conn, key, run_date, ad_count, days,
                                     prev_ad_count=(int(base) if base not in (None, 0) else None),
                                     flagged=is_flag)
                series = store.history_series(conn, key)

                if is_flag:
                    flagged += 1
                    print(f"  ⚠️ {title[:34]:34} {ad_count} ativos (antes {base}) — SUSPEITO, "
                          f"Notion não atualizado")
                    try:
                        notion.pages.update(page_id=key, properties={
                            P_HIST: {"rich_text": [{"type": "text",
                                     "text": {"content": _spark(series, flagged=True)}}]}})
                    except Exception as e:
                        print(f"     ! Notion: {e}")
                    time.sleep(0.34)
                    continue

                main_props = {
                    P_ADS: {"number": ad_count},
                    P_DAYS: {"number": days},
                    P_CHECKED: {"date": {"start": run_date}},
                    P_HIST: {"rich_text": [{"type": "text",
                             "text": {"content": _spark(series)}}]},
                    P_TREND: {"select": {"name": _trend(series)}},
                }
                if delta is not None:
                    main_props[P_DELTA] = {"number": delta}
                try:
                    notion.pages.update(page_id=key, properties=main_props)
                    ok += 1
                except Exception as e:
                    print(f"  ! {title[:34]:34} Notion update: {e}")
                    errors += 1
                time.sleep(0.34)

                # Snapshot diário no banco 📊 HISTÓRICO ANÚNCIOS: DESLIGADO
                # (Julio pediu — "no Notion não precisa de snapshot"). O histórico
                # continua no SQLite (offer_history) + na coluna HISTÓRICO do banco
                # principal ("22→33→20"). Pra religar: setar `write_snapshots`.
                write_snapshots = False
                if write_snapshots and hist_db:
                    hp = {
                        "Name": {"title": [{"type": "text",
                                  "text": {"content": f"{title[:80]} · {run_date}"}}]},
                        P_TITLE: {"relation": [{"id": key}]},
                        "DATA": {"date": {"start": run_date}},
                        "ANÚNCIOS ATIVOS": {"number": ad_count},
                        "DIAS ATIVOS": {"number": days},
                    }
                    if delta is not None:
                        hp["VARIAÇÃO"] = {"number": delta}
                    try:
                        existing = hist_today.get(key)
                        if existing:
                            notion.pages.update(page_id=existing, properties=hp)
                        else:
                            notion.pages.create(
                                parent={"database_id": hist_db}, properties=hp)
                    except Exception as e:
                        print(f"     ! histórico: {e}")
                    time.sleep(0.34)

                d = f"  Δ {delta:+d}" if delta is not None else ""
                print(f"  + {title[:34]:34} {ad_count:>4} ativos · {days}d{d}")
    except PlaywrightMissing as e:
        raise SystemExit(str(e))

    print(f"\nRecálculo: {ok} atualizadas, {flagged} suspeitas (não escritas), {errors} erros.")
