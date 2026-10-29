"""Fluxo do `run` com um Miner falso (sem rede): passadas, frases e dry-run não podem quebrar."""
import argparse

from minerador import __main__ as mn


class FakeMiner:
    calls = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def search_keywords(self, win, countries, deadline=None):
        FakeMiner.calls.append((tuple(win), self_scrolls[0]))
        return []

    def verify_many(self, items, deadline=None):
        return {}


self_scrolls = [0]


def test_run_walks_all_scroll_passes_and_ends_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(mn, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mn, "Miner", FakeMiner)
    monkeypatch.setattr(mn, "_auto_reconcile", lambda *a: None)
    real_load = mn.Config.load

    def load():
        cfg = real_load()
        cfg.keywords, cfg.keywords_reserve = ["a b c d", "e f g h"], []
        cfg.keyword_window = 1
        cfg.scroll_passes = [24, 40, 60]
        orig = FakeMiner.search_keywords

        def spy(self, win, countries, deadline=None):
            self_scrolls[0] = cfg.fetch.max_scrolls
            return orig(self, win, countries, deadline)
        monkeypatch.setattr(FakeMiner, "search_keywords", spy)
        return cfg

    monkeypatch.setattr(mn.Config, "load", staticmethod(load))
    args = argparse.Namespace(keyword=None, target=20, sync_target=None, window=None,
                              deadline=5, max_scrolls=None, dry_run=True, progress=False)
    mn.cmd_run(args)
    assert sorted({s for _, s in FakeMiner.calls}) == [24, 40, 60]
