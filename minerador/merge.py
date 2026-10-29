"""Junta os bancos dos jobs paralelos no banco principal e dá a nota (Groq) nas ofertas novas."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from . import nota, store


def merge_dbs(main_path: Path, job_paths) -> int:
    """Une synced/blocked/rejected/offer_text/offer_history (+ cursores kw_cursor_*) dos
    bancos dos jobs no principal. Em conflito de synced, vale o synced_at mais recente.
    Devolve quantas ofertas NOVAS entraram em synced."""
    main = store.connect(Path(main_path))
    before = {r[0] for r in main.execute("SELECT offer_key FROM synced")}
    for jp in job_paths:
        jp = Path(jp)
        if not jp.exists():
            continue
        main.execute("ATTACH DATABASE ? AS j", (str(jp),))
        try:
            main.execute("""INSERT INTO synced SELECT * FROM j.synced WHERE true
                            ON CONFLICT(offer_key) DO UPDATE SET
                              page_name=excluded.page_name, domain=excluded.domain,
                              notion_page_id=excluded.notion_page_id, ad_count=excluded.ad_count,
                              days_active_max=excluded.days_active_max, synced_at=excluded.synced_at
                            WHERE excluded.synced_at > synced.synced_at""")
            main.execute("INSERT OR IGNORE INTO blocked SELECT * FROM j.blocked")
            main.execute("""INSERT INTO rejected SELECT * FROM j.rejected WHERE true
                            ON CONFLICT(page_id, domain_root) DO UPDATE SET
                              reason=excluded.reason, hard=excluded.hard, rejected_at=excluded.rejected_at
                            WHERE excluded.rejected_at > rejected.rejected_at""")
            main.execute("INSERT OR IGNORE INTO offer_text SELECT * FROM j.offer_text")
            main.execute("INSERT OR IGNORE INTO offer_history SELECT * FROM j.offer_history")
            main.execute("INSERT OR REPLACE INTO kv SELECT * FROM j.kv WHERE key LIKE 'kw_cursor_%'")
            main.commit()
        except sqlite3.Error as e:
            print(f"  ! merge de {jp.name} falhou: {e}")
        finally:
            main.execute("DETACH DATABASE j")
    after = {r[0] for r in main.execute("SELECT offer_key FROM synced")}
    main.close()
    return len(after - before)


def score_pending(conn, cfg, notion, sleep_s: float = 6.5) -> int:
    """Nota (Groq) nas ofertas novas e escreve as 7 colunas na página do Notion.
    Sem GROQ_API_KEY ou com erro: não escreve nada (colunas vazias)."""
    from .notion_sync import nota_props
    if not cfg.groq_api_key:
        print("  (sem GROQ_API_KEY — ofertas ficam sem nota)")
        return 0
    done = 0
    rows = store.pending_scoring(conn)
    print(f"  nota: {len(rows)} oferta(s) pendente(s)")
    for r in rows:
        notas = nota.avaliar(r["text"], cfg.groq_api_key, cfg.groq_model)
        ok = notas is not None
        if ok:
            try:
                notion.pages.update(page_id=r["notion_page_id"], properties=nota_props(notas))
                done += 1
            except Exception as e:
                ok = False
                print(f"  ! nota não gravada no Notion ({r['offer_key']}): {e}")
        store.mark_scored(conn, r["offer_key"], ok)
        time.sleep(sleep_s)       # plano grátis: ~10 requisições/min
    return done
