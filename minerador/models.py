from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone


def _today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass
class Ad:
    ad_archive_id: str
    page_id: str = ""
    page_name: str = ""
    page_categories: list = field(default_factory=list)
    body_text: str = ""
    title: str = ""
    link_url: str = ""
    caption: str = ""
    domain: str = ""
    cta_text: str = ""
    cta_type: str = ""
    start_date: int | None = None
    end_date: int | None = None
    total_active_time: int | None = None   # segundos, calculado pela Meta
    is_active: bool = True
    publisher_platform: list = field(default_factory=list)
    collation_count: int = 1
    page_like_count: int = 0
    media_url: str = ""
    keyword: str = ""
    country: str = ""

    @property
    def days_active(self) -> int:
        d = 0
        if self.start_date:
            try:
                start = date.fromtimestamp(self.start_date)
                end = _today()
                if self.end_date:
                    try:
                        end = date.fromtimestamp(self.end_date)
                    except (OSError, OverflowError, ValueError):
                        pass
                d = max((end - start).days, 0)
            except (OSError, OverflowError, ValueError):
                d = 0
        if self.total_active_time:
            d = max(d, int(self.total_active_time) // 86400)
        return d


@dataclass
class Offer:
    page_id: str
    page_name: str
    domain: str
    link_url: str
    ad_count: int
    days_active_max: int
    collation_total: int
    platforms: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    countries: list = field(default_factory=list)
    sample_copy: str = ""
    media_url: str = ""
    page_categories: list = field(default_factory=list)
    page_like_count: int = 0
    started_recently: bool = False
    # preenchidos pelo filtro forte (salespage.py) — transitórios, não persistem
    price_brl: float | None = None
    checkout_host: str = ""
    reject_reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.page_id or self.page_name or '?'}|{self.domain}"

    def library_url(self) -> str:
        c = self.countries[0] if self.countries else "BR"
        base = ("https://www.facebook.com/ads/library/"
                f"?active_status=active&ad_type=all&country={c}")
        if self.page_id:
            return f"{base}&view_all_page_id={self.page_id}"
        return f"{base}&q={self.domain}"
