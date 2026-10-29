from datetime import datetime, timedelta, timezone

from minerador import store
from minerador.merge import merge_dbs
from minerador.notion_sync import nota_props
from minerador import nota


def _db(tmp_path, name):
    return store.connect(tmp_path / name)


def _synced(c, key, at, pid="n1"):
    c.execute("INSERT INTO synced (offer_key,page_name,domain,notion_page_id,ad_count,days_active_max,synced_at)"
              " VALUES (?,?,?,?,?,?,?)", (key, "x", "d.com", pid, 10, 5, at))
    c.commit()


def test_merge_unions_synced_and_counts_new(tmp_path):
    main, j1, j2 = _db(tmp_path, "m.db"), _db(tmp_path, "j1.db"), _db(tmp_path, "j2.db")
    _synced(main, "1|a.com", "2026-10-01T00:00:00+00:00")
    _synced(j1, "2|b.com", "2026-10-29T00:00:00+00:00")
    _synced(j2, "3|c.com", "2026-10-29T00:00:00+00:00")
    for c in (main, j1, j2):
        c.close()
    assert merge_dbs(tmp_path / "m.db", [tmp_path / "j1.db", tmp_path / "j2.db"]) == 2
    m = store.connect(tmp_path / "m.db")
    assert {r["offer_key"] for r in store.all_synced(m)} == {"1|a.com", "2|b.com", "3|c.com"}


def test_merge_keeps_latest_synced_at(tmp_path):
    main, j1 = _db(tmp_path, "m.db"), _db(tmp_path, "j1.db")
    _synced(main, "1|a.com", "2026-10-01T00:00:00+00:00", pid="old")
    _synced(j1, "1|a.com", "2026-10-29T00:00:00+00:00", pid="new")
    main.close(); j1.close()
    merge_dbs(tmp_path / "m.db", [tmp_path / "j1.db"])
    m = store.connect(tmp_path / "m.db")
    assert m.execute("SELECT notion_page_id FROM synced").fetchone()[0] == "new"


def test_merge_unions_rejected_blocked_and_text(tmp_path):
    main, j1 = _db(tmp_path, "m.db"), _db(tmp_path, "j1.db")
    store.reject(j1, "7", "loja.com.br", "loja", hard=True)
    j1.execute("INSERT INTO blocked VALUES ('9|z.com','9','z.com','2026-10-29')")
    store.save_offer_text(j1, "2|b.com", "texto da oferta")
    j1.commit(); main.close(); j1.close()
    merge_dbs(tmp_path / "m.db", [tmp_path / "j1.db"])
    m = store.connect(tmp_path / "m.db")
    assert "7" in store.rejected_sets(m)[0]
    assert m.execute("SELECT COUNT(*) FROM blocked").fetchone()[0] == 1
    assert m.execute("SELECT text FROM offer_text").fetchone()[0] == "texto da oferta"


def test_merge_empty_or_missing_job_db_ok(tmp_path):
    main = _db(tmp_path, "m.db"); main.close()
    assert merge_dbs(tmp_path / "m.db", [tmp_path / "nao_existe.db"]) == 0


def test_pending_scoring_needs_notion_page_and_limits_tries(tmp_path):
    c = _db(tmp_path, "m.db")
    _synced(c, "2|b.com", "2026-10-29T00:00:00+00:00", pid="pg")
    store.save_offer_text(c, "2|b.com", "t")
    assert [r["offer_key"] for r in store.pending_scoring(c)] == ["2|b.com"]
    for _ in range(3):
        store.mark_scored(c, "2|b.com", ok=False)
    assert store.pending_scoring(c) == []


def test_nota_props_empty_when_none_and_seven_numbers():
    assert nota_props(None) == {}
    full = {c: 8 for c in nota.CRITERIOS}
    props = nota_props(full)
    assert len(props) == 7 and props["NOTA MÉDIA"] == {"number": 8.0}
    assert all("number" in v for v in props.values())
