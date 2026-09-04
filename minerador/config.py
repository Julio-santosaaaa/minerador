from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "minerador.db"
PROFILE_DIR = DATA_DIR / "pw-profile"

_DEFAULT_WEIGHTS = {
    "days_active": 0.40, "creative_count": 0.30, "collation": 0.20, "recency": 0.10,
}


@dataclass
class FetchCfg:
    headless: bool = True
    max_scrolls: int = 6
    verify_scrolls: int = 6
    recalc_scrolls: int = 6
    results_per_keyword_cap: int = 250
    delay_seconds: tuple = (1.0, 2.0)
    parallel_tabs: int = 1        # nº de abas/navegadores na MINERAÇÃO (recalc é sempre 1)
    salespage_timeout_ms: int = 9000   # teto pra abrir cada página de vendas (filtro forte)
    proxy: str | None = None


@dataclass
class Config:
    countries: list = field(default_factory=lambda: ["BR", "US", "ES", "MX"])
    active_status: str = "active"
    keywords: list = field(default_factory=list)
    keywords_reserve: list = field(default_factory=list)
    recycle_days: int = 15
    price_ceiling_brl: float = 97.0
    competitor_page_ids: list = field(default_factory=list)
    ignore_domains: list = field(default_factory=list)
    min_ads: int = 10
    max_ads: int = 99
    infoproduct_only: bool = True
    verify_pages: bool = True
    verify_mode: str = "borderline"   # always | borderline | never
    daily_target: int = 20
    sync_target: int = 20
    fallback_max_ads: int = 400
    keyword_window: int = 10
    run_deadline_min: int = 75
    fetch: FetchCfg = field(default_factory=FetchCfg)
    heat_weights: dict = field(default_factory=lambda: dict(_DEFAULT_WEIGHTS))
    min_days_active: int = 7
    notion_database_id: str = ""
    notion_history_database_id: str = ""
    notion_history_data_source_id: str = ""
    notion_write_history_snapshots: bool = False
    notion_token: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        load_dotenv(ROOT / ".env")
        path = path or (ROOT / "config.yaml")
        if not path.exists():
            raise SystemExit(f"config.yaml não encontrado em {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        f = raw.get("fetch") or {}
        ds = f.get("delay_seconds") or [1, 2]
        fetch = FetchCfg(
            headless=bool(f.get("headless", True)),
            max_scrolls=int(f.get("max_scrolls", 6)),
            verify_scrolls=int(f.get("verify_scrolls", 6)),
            recalc_scrolls=int(f.get("recalc_scrolls", f.get("verify_scrolls", 6))),
            results_per_keyword_cap=int(f.get("results_per_keyword_cap", 250)),
            delay_seconds=(float(ds[0]), float(ds[1])),
            parallel_tabs=max(1, int(f.get("parallel_tabs", 1))),
            salespage_timeout_ms=int(f.get("salespage_timeout_ms", 9000)),
            proxy=(f.get("proxy") or None),
        )

        # overrides por env (usado no job de nuvem pra ir mais devagar contra bloqueio)
        if os.getenv("MINERADOR_TABS"):
            fetch.parallel_tabs = max(1, int(os.getenv("MINERADOR_TABS")))
        if os.getenv("MINERADOR_DELAY"):
            lo, hi = os.getenv("MINERADOR_DELAY").split(",")
            fetch.delay_seconds = (float(lo), float(hi))
        if os.getenv("MINERADOR_HEADLESS"):
            fetch.headless = os.getenv("MINERADOR_HEADLESS") not in ("0", "false", "")

        def _clean(key):
            return [str(x).strip() for x in (raw.get(key) or []) if x and str(x).strip()]

        # dedup preservando ordem
        seen, kws = set(), []
        for k in _clean("keywords"):
            lk = k.lower()
            if lk not in seen:
                seen.add(lk)
                kws.append(k)
        # reserva: dedup contra si mesma E contra as principais
        reserve = []
        for k in _clean("keywords_reserve"):
            lk = k.lower()
            if lk not in seen:
                seen.add(lk)
                reserve.append(k)

        weights = dict(_DEFAULT_WEIGHTS)
        weights.update(raw.get("heat_weights") or {})

        return cls(
            countries=[c.upper() for c in _clean("countries")] or ["BR"],
            active_status=str(raw.get("active_status", "active")),
            keywords=kws,
            keywords_reserve=reserve,
            recycle_days=int(raw.get("recycle_days", 15)),
            price_ceiling_brl=float(raw.get("price_ceiling_brl", 97)),
            competitor_page_ids=_clean("competitor_page_ids"),
            ignore_domains=[d.lower().lstrip(".") for d in _clean("ignore_domains")],
            min_ads=int(raw.get("min_ads", 10)),
            max_ads=int(raw.get("max_ads", 99)),
            infoproduct_only=bool(raw.get("infoproduct_only", True)),
            verify_pages=bool(raw.get("verify_pages", True)),
            verify_mode=str(raw.get("verify_mode", "borderline")).strip().lower(),
            daily_target=int(raw.get("daily_target", 20)),
            sync_target=int(raw.get("sync_target", raw.get("daily_target", 20))),
            fallback_max_ads=int(raw.get("fallback_max_ads", 400)),
            keyword_window=int(raw.get("keyword_window", 10)),
            run_deadline_min=int(raw.get("run_deadline_min", 75)),
            fetch=fetch,
            heat_weights=weights,
            min_days_active=int(raw.get("min_days_active", 7)),
            notion_database_id=str((raw.get("notion") or {}).get("database_id", "") or ""),
            notion_history_database_id=str((raw.get("notion") or {}).get("history_database_id", "") or ""),
            notion_history_data_source_id=str((raw.get("notion") or {}).get("history_data_source_id", "") or ""),
            notion_write_history_snapshots=bool((raw.get("notion") or {}).get("write_history_snapshots", False)),
            notion_token=os.getenv("NOTION_TOKEN", ""),
        )
