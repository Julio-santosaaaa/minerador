from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    keywords TEXT,
    ad_count INTEGER DEFAULT 0,
    offer_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ads (
    ad_archive_id TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    seen_at TEXT NOT NULL,
    target TEXT,
    page_id TEXT,
    page_name TEXT,
    domain TEXT,
    link_url TEXT,
    body_text TEXT,
    days_active INTEGER,
    collation_count INTEGER,
    is_active INTEGER,
    platforms TEXT,
    country TEXT,
    start_date INTEGER,
    media_url TEXT,
    PRIMARY KEY (ad_archive_id, run_id, country)
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS synced (
    offer_key TEXT PRIMARY KEY,
    page_name TEXT,
    domain TEXT,
    notion_page_id TEXT,
    ad_count INTEGER,
    days_active_max INTEGER,
    synced_at TEXT
);
CREATE TABLE IF NOT EXISTS offer_history (
    offer_key TEXT NOT NULL,
    run_date TEXT NOT NULL,          -- YYYY-MM-DD (fuso America/Sao_Paulo, UTC-3)
    ad_count INTEGER,
    days_active INTEGER,
    prev_ad_count INTEGER,
    delta INTEGER,
    flagged INTEGER DEFAULT 0,       -- 1 = suspeito (0 anúncios ou pulo > 10x); não escrito no Notion
    checked_at TEXT,
    PRIMARY KEY (offer_key, run_date)
);
CREATE TABLE IF NOT EXISTS offers (
    offer_key TEXT PRIMARY KEY,
    page_id TEXT,
    page_name TEXT,
    domain TEXT,
    link_url TEXT,
    ad_count INTEGER,
    days_active_max INTEGER,
    collation_total INTEGER,
    platforms TEXT,
    keywords TEXT,
    countries TEXT,
    sample_copy TEXT,
    media_url TEXT,
    page_categories TEXT,
    page_like_count INTEGER DEFAULT 0,
    heat REAL,
    level TEXT,
    first_seen TEXT,
    last_seen TEXT,
    notion_page_id TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# colunas adicionadas depois da v0.1 -> ALTER TABLE se faltarem
_MIGRATIONS = {
    "offers": {"page_like_count": "INTEGER DEFAULT 0", "countries": "TEXT"},
    "ads": {"country": "TEXT"},
}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for table, cols in _MIGRATIONS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols.items():
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    # ofertas já enviadas ao Notion saem de 'offers' e ficam só em 'synced'
    # (mantém a dedup sem inchar a tabela de trabalho)
    conn.execute(
        """INSERT OR IGNORE INTO synced
             (offer_key, page_name, domain, notion_page_id, ad_count, days_active_max, synced_at)
           SELECT offer_key, page_name, domain, notion_page_id, ad_count, days_active_max, last_seen
           FROM offers WHERE notion_page_id IS NOT NULL AND notion_page_id != ''""")
    conn.execute("DELETE FROM offers WHERE notion_page_id IS NOT NULL AND notion_page_id != ''")
    conn.commit()
    return conn


def start_run(conn, keywords) -> int:
    cur = conn.execute("INSERT INTO runs (started_at, keywords) VALUES (?, ?)",
                       (now_iso(), ", ".join(keywords)))
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id, ad_count, offer_count) -> None:
    conn.execute("UPDATE runs SET finished_at=?, ad_count=?, offer_count=? WHERE id=?",
                 (now_iso(), ad_count, offer_count, run_id))
    conn.commit()


def save_ads(conn, run_id, ads) -> None:
    ts = now_iso()
    rows = [(
        a.ad_archive_id, run_id, ts, a.keyword, a.page_id, a.page_name, a.domain,
        a.link_url, a.body_text[:2000], a.days_active, a.collation_count,
        int(a.is_active), ",".join(a.publisher_platform), a.country or "",
        a.start_date or 0, a.media_url,
    ) for a in ads]
    conn.executemany(
        """INSERT OR REPLACE INTO ads
           (ad_archive_id, run_id, seen_at, target, page_id, page_name, domain, link_url,
            body_text, days_active, collation_count, is_active, platforms, country,
            start_date, media_url)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def upsert_offer(conn, offer, heat_val, level_val) -> bool:
    row = conn.execute(
        "SELECT first_seen, notion_page_id FROM offers WHERE offer_key=?",
        (offer.key,),
    ).fetchone()
    ts = now_iso()
    first_seen = row["first_seen"] if row else ts
    notion_page_id = row["notion_page_id"] if row else None
    is_new = row is None

    conn.execute(
        """INSERT INTO offers
             (offer_key, page_id, page_name, domain, link_url, ad_count, days_active_max,
              collation_total, platforms, keywords, countries, sample_copy, media_url,
              page_categories, page_like_count, heat, level, first_seen, last_seen,
              notion_page_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(offer_key) DO UPDATE SET
             page_id=excluded.page_id, page_name=excluded.page_name,
             link_url=excluded.link_url, ad_count=excluded.ad_count,
             days_active_max=excluded.days_active_max,
             collation_total=excluded.collation_total, platforms=excluded.platforms,
             keywords=excluded.keywords, countries=excluded.countries,
             sample_copy=excluded.sample_copy,
             media_url=excluded.media_url, page_categories=excluded.page_categories,
             page_like_count=excluded.page_like_count,
             heat=excluded.heat, level=excluded.level, last_seen=excluded.last_seen""",
        (
            offer.key, offer.page_id, offer.page_name, offer.domain, offer.link_url,
            offer.ad_count, offer.days_active_max, offer.collation_total,
            ",".join(offer.platforms), ", ".join(offer.keywords),
            ",".join(offer.countries), offer.sample_copy,
            offer.media_url, ", ".join(offer.page_categories), offer.page_like_count,
            heat_val, level_val, first_seen, ts, notion_page_id,
        ),
    )
    conn.commit()
    return is_new


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(conn, key, value) -> None:
    conn.execute("INSERT INTO kv (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    conn.commit()


def synced_keys(conn, exclude_stale_days: int = 0) -> set:
    """Ofertas que já foram pro Notion (não re-minerar).
    `exclude_stale_days > 0`: ofertas sincronizadas há mais de N dias saem do
    conjunto → voltam a poder ser mineradas (reciclagem). O vínculo com a página
    do Notion continua em `synced`, então re-minerar ATUALIZA a página, não duplica."""
    cutoff = None
    if exclude_stale_days > 0:
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=exclude_stale_days)).isoformat(timespec="seconds")
    keys = set()
    for r in conn.execute("SELECT offer_key, synced_at FROM synced"):
        if cutoff and r["synced_at"] and r["synced_at"] < cutoff:
            continue
        keys.add(r["offer_key"])
    keys |= {r["offer_key"] for r in conn.execute(
        "SELECT offer_key FROM offers WHERE notion_page_id IS NOT NULL AND notion_page_id != ''")}
    return keys


def archive_offer(conn, offer_key, notion_page_id) -> None:
    """Move a oferta de 'offers' -> 'synced' e apaga de 'offers'."""
    row = conn.execute(
        "SELECT page_name, domain, ad_count, days_active_max FROM offers WHERE offer_key=?",
        (offer_key,)).fetchone()
    conn.execute(
        """INSERT INTO synced
             (offer_key, page_name, domain, notion_page_id, ad_count, days_active_max, synced_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(offer_key) DO UPDATE SET
             notion_page_id=excluded.notion_page_id, synced_at=excluded.synced_at""",
        (offer_key,
         row["page_name"] if row else "",
         row["domain"] if row else "",
         notion_page_id,
         row["ad_count"] if row else 0,
         row["days_active_max"] if row else 0,
         now_iso()))
    conn.execute("DELETE FROM offers WHERE offer_key=?", (offer_key,))
    conn.commit()


def get_notion_page_id(conn, offer_key):
    row = conn.execute("SELECT notion_page_id FROM offers WHERE offer_key=?",
                       (offer_key,)).fetchone()
    if row and row["notion_page_id"]:
        return row["notion_page_id"]
    # oferta reciclada: o vínculo ficou em 'synced' → reusa a mesma página do Notion
    row = conn.execute("SELECT notion_page_id FROM synced WHERE offer_key=?",
                       (offer_key,)).fetchone()
    return row["notion_page_id"] if row and row["notion_page_id"] else None


def set_notion_page_id(conn, offer_key, page_id) -> None:
    conn.execute("UPDATE offers SET notion_page_id=? WHERE offer_key=?",
                 (page_id, offer_key))
    conn.commit()


def forget_synced(conn, offer_keys) -> int:
    """Remove essas ofertas de 'synced' e zera notion_page_id em 'offers'
    (Julio apagou a linha no Notion → pode ser re-minerada do zero)."""
    keys = list(offer_keys)
    if not keys:
        return 0
    q = ",".join("?" for _ in keys)
    cur = conn.execute(f"DELETE FROM synced WHERE offer_key IN ({q})", keys)
    conn.execute(f"UPDATE offers SET notion_page_id=NULL WHERE offer_key IN ({q})", keys)
    conn.commit()
    return cur.rowcount


def all_synced(conn):
    return conn.execute(
        "SELECT offer_key, page_name, domain, notion_page_id FROM synced").fetchall()


def list_offers(conn, min_heat: float = 0.0):
    return conn.execute(
        "SELECT * FROM offers WHERE heat >= ? ORDER BY heat DESC, days_active_max DESC",
        (min_heat,),
    ).fetchall()


# ---- tracker de progresso (offer_history) --------------------------------

def record_history(conn, offer_key, run_date, ad_count, days_active,
                   prev_ad_count=None, flagged=False) -> None:
    """Grava (ou sobrescreve) o snapshot do dia pra uma oferta.
    Chave = (offer_key, run_date): rodar 2x no mesmo dia atualiza, não duplica."""
    delta = None
    if prev_ad_count is not None and ad_count is not None:
        delta = ad_count - prev_ad_count
    conn.execute(
        """INSERT INTO offer_history
             (offer_key, run_date, ad_count, days_active, prev_ad_count, delta, flagged, checked_at)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(offer_key, run_date) DO UPDATE SET
             ad_count=excluded.ad_count, days_active=excluded.days_active,
             prev_ad_count=excluded.prev_ad_count, delta=excluded.delta,
             flagged=excluded.flagged, checked_at=excluded.checked_at""",
        (offer_key, run_date, ad_count, days_active, prev_ad_count, delta,
         int(bool(flagged)), now_iso()),
    )
    conn.commit()


def history_series(conn, offer_key, limit: int = 12) -> list:
    """Últimos N contadores válidos (não-flagged), do mais antigo pro mais novo."""
    rows = conn.execute(
        """SELECT ad_count FROM offer_history
           WHERE offer_key=? AND flagged=0 AND ad_count IS NOT NULL
           ORDER BY run_date DESC LIMIT ?""",
        (offer_key, limit),
    ).fetchall()
    return [r["ad_count"] for r in reversed(rows)]


def last_valid_count(conn, offer_key):
    """Contagem mais recente não-suspeita (fallback quando o Notion não tem número)."""
    row = conn.execute(
        """SELECT ad_count FROM offer_history
           WHERE offer_key=? AND flagged=0 AND ad_count IS NOT NULL
           ORDER BY run_date DESC LIMIT 1""",
        (offer_key,),
    ).fetchone()
    return row["ad_count"] if row else None
