from datetime import datetime, timedelta, timezone

from minerador import store


def _conn(tmp_path):
    return store.connect(tmp_path / "t.db")


def _age(conn, days):
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    conn.execute("UPDATE rejected SET rejected_at=?", (old,))
    conn.commit()


def test_hard_reject_blocks_within_14_days(tmp_path):
    c = _conn(tmp_path)
    store.reject(c, "123", "lp.loja.com.br", "loja", hard=True)
    pages, domains = store.rejected_sets(c)
    assert "123" in pages and store.root_domain("lp.loja.com.br") in domains


def test_soft_reject_expires_after_2_days(tmp_path):
    c = _conn(tmp_path)
    store.reject(c, "9", "a.com", "não abriu", hard=False)
    _age(c, 3)
    pages, domains = store.rejected_sets(c)
    assert "9" not in pages and "a.com" not in domains


def test_hard_reject_expires_after_14_days(tmp_path):
    c = _conn(tmp_path)
    store.reject(c, "9", "a.com", "loja", hard=True)
    _age(c, 15)
    assert store.rejected_sets(c) == (set(), set())


def test_shared_hosts_never_block_other_offers(tmp_path):
    c = _conn(tmp_path)
    store.reject(c, "1", "pay.hotmart.com", "loja", hard=True)
    store.reject(c, "2", "x.vercel.app", "loja", hard=True)
    pages, domains = store.rejected_sets(c)
    assert pages == {"1", "2"} and domains == set()
    assert store.root_domain("pay.hotmart.com") == ""
    assert store.root_domain("projetos.minhaloja.com.br") == "minhaloja.com.br"
