from __future__ import annotations

import json
import random
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote

from .config import Config
from .parse import iter_ad_nodes

_SCRIPT_JSON = re.compile(r'<script[^>]+type="application/json"[^>]*>(.*?)</script>', re.S)

_KEYWORD_URL = (
    "https://www.facebook.com/ads/library/"
    "?active_status={status}&ad_type=all&country={country}"
    "&media_type=all&search_type=keyword_unordered&q={q}"
)
_PAGE_URL = (
    "https://www.facebook.com/ads/library/"
    "?active_status={status}&ad_type=all&country={country}"
    "&media_type=all&view_all_page_id={pid}"
)
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
_COOKIE_LABELS = [
    "Permitir todos os cookies", "Allow all cookies", "Recusar cookies opcionais",
    "Decline optional cookies", "Only allow essential cookies", "Permitir cookies essenciais",
]
_JSON_PREFIXES = ("for (;;);", "for(;;);", ")]}'")

# só precisamos do JSON do GraphQL — imagem/vídeo/fonte/CSS são peso morto
_BLOCK_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}


class PlaywrightMissing(RuntimeError):
    pass


def _scan_count(objs) -> int:
    """Maior valor inteiro sob a chave `count` no JSON do GraphQL.
    É o número EXATO que a biblioteca mostra no header ('≈ X resultados')
    e já vem na primeira resposta — não precisa rolar a tela."""
    best = 0
    stack = list(objs)
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            v = cur.get("count")
            if isinstance(v, bool):
                pass
            elif isinstance(v, int):
                best = max(best, v)
            elif isinstance(v, str) and v.isdigit():
                best = max(best, int(v))
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)
    return best


def _iter_json_objects(text: str):
    text = text.strip()
    for pref in _JSON_PREFIXES:
        if text.startswith(pref):
            text = text[len(pref):].strip()
    if not text:
        return
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \r\n\t":
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            nl = text.find("\n", i)
            if nl == -1:
                break
            i = nl + 1
            continue
        yield obj
        i = end


# ---------------------------------------------------------------------------
# Coleta paralela (2+ abas): cada worker roda em sua própria thread com seu
# próprio Playwright/browser/context/page. Nada é compartilhado entre threads
# além do dict de resultados (protegido por lock).
# ---------------------------------------------------------------------------

def _drain_into(pending, captured) -> None:
    # NB: resp.text() no Playwright sync não tem timeout e é preso à greenlet
    # que o criou (não dá pra chamar de outra thread). Se um corpo nunca chega
    # (bloqueio de IP), essa chamada trava — quem protege contra isso é o
    # hard_cap do collect_many (join com teto) + threads daemon.
    while pending:
        kind, resp = pending.pop(0)
        try:
            body = resp.text()
        except Exception:
            continue
        if not body or "ad_archive_id" not in body:
            continue
        if kind == "json":
            for obj in _iter_json_objects(body):
                captured.append(obj)
        else:
            for m in _SCRIPT_JSON.finditer(body):
                try:
                    captured.append(json.loads(m.group(1)))
                except ValueError:
                    pass


def _dismiss_cookies(page) -> None:
    for lab in _COOKIE_LABELS:
        try:
            btn = page.get_by_role("button", name=lab)
            if btn.count():
                btn.first.click(timeout=2500)
                page.wait_for_timeout(1200)
                return
        except Exception:
            pass


def _do_collect(page, pending, captured, cfg, url, scrolls, label, cookies_done,
                deadline=None) -> tuple:
    pending.clear()
    captured.clear()
    if deadline and time.time() > deadline:
        return [], 0
    try:
        page.set_default_timeout(45_000)
    except Exception:
        pass
    try:
        page.goto(url, wait_until="commit", timeout=45_000)
    except Exception as e:
        print(f"  ! {label}: falha ao abrir ({e})")
        return [], 0
    page.wait_for_timeout(1500)
    if not cookies_done[0]:
        _dismiss_cookies(page)
        cookies_done[0] = True
    _drain_into(pending, captured)
    lo, hi = cfg.fetch.delay_seconds
    cap = cfg.fetch.results_per_keyword_cap * 4
    last, stag = -1, 0
    for _ in range(scrolls):
        if deadline and time.time() > deadline:
            break
        try:
            page.mouse.wheel(0, 4400)
        except Exception:
            break
        page.wait_for_timeout(int(random.uniform(lo, hi) * 1000))
        _drain_into(pending, captured)
        cnt = len(captured)
        if cnt == last:
            stag += 1
            if stag >= 2:
                break
        else:
            stag = 0
        last = cnt
        if cnt > cap:
            break
    count = _scan_count(list(captured))
    return list(iter_ad_nodes(list(captured))), count


def _worker(cfg, raw_dir, tasks, results, lock, deadline=None) -> None:
    from playwright.sync_api import sync_playwright
    pending, captured = [], []

    def on_response(resp):
        try:
            req = resp.request
            if "graphql" in resp.url and req.method == "POST":
                pending.append(("json", resp))
            elif req.resource_type == "document" and "/ads/library" in resp.url:
                pending.append(("html", resp))
        except Exception:
            return

    def route(r):
        try:
            if r.request.resource_type in _BLOCK_RESOURCE_TYPES:
                r.abort()
                return
        except Exception:
            pass
        try:
            r.continue_()
        except Exception:
            pass

    proxy = {"server": cfg.fetch.proxy} if cfg.fetch.proxy else None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=cfg.fetch.headless, proxy=proxy,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = browser.new_context(
            locale="pt-BR", user_agent=_UA, viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
        page = ctx.new_page()
        page.route("**/*", route)
        page.on("response", on_response)
        cookies_done = [False]
        for key, url, scrolls, label in tasks:
            if deadline and time.time() > deadline:
                print(f"  (tempo limite — pulando {label} e o resto)")
                break
            nodes, count = _do_collect(page, pending, captured, cfg, url, scrolls,
                                       label, cookies_done, deadline)
            print(f"  · {label}: {len(nodes)} anúncios")
            if not nodes:
                _dump_empty(raw_dir, label, captured)
            with lock:
                results[key] = (nodes, count)
            time.sleep(random.uniform(*cfg.fetch.delay_seconds))
        try:
            page.unroute("**/*")
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


def collect_many(cfg, raw_dir, tasks, workers: int = 2, deadline=None) -> dict:
    """tasks: [(key, url, scrolls, label), ...] -> {key: ([nodes], count)}.
    Distribui as tasks entre `workers` threads (round-robin), cada uma com
    seu próprio browser. Threads daemon + join com teto de tempo: se um worker
    travar (corpo de resposta que nunca chega / bloqueio de IP), a rodada segue
    com o que já coletou em vez de pendurar pra sempre."""
    workers = max(1, min(workers, len(tasks)))
    results, lock = {}, threading.Lock()
    slices = [tasks[i::workers] for i in range(workers)]
    threads = [threading.Thread(target=_worker,
                                args=(cfg, raw_dir, s, results, lock, deadline),
                                daemon=True)
               for s in slices if s]
    for t in threads:
        t.start()

    # teto: ~50s por task da maior fatia (+ margem), nunca além do deadline da rodada
    biggest = max((len(s) for s in slices), default=0)
    hard_cap = time.time() + max(150, biggest * 50)
    if deadline:
        hard_cap = min(hard_cap, deadline + 90)
    for t in threads:
        remaining = hard_cap - time.time()
        if remaining > 0:
            t.join(timeout=remaining)
    alive = [t for t in threads if t.is_alive()]
    if alive:
        print(f"  ⚠️ {len(alive)} aba(s) travada(s) — seguindo com "
              f"{len(results)}/{len(tasks)} resultados coletados")
    return results


class Miner:
    """Sessão de browser reaproveitada por buscas de palavra-chave e verificação de página."""

    def __init__(self, cfg: Config, raw_dir: Path):
        self.cfg = cfg
        self.raw_dir = raw_dir
        raw_dir.mkdir(parents=True, exist_ok=True)
        self._pending: list = []
        self._captured: list = []
        self._cookies_done = False
        self.last_result_count = 0   # nº exato de anúncios da última busca (campo `count`)

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise PlaywrightMissing(
                "Playwright não instalado. Rode:\n"
                "  pip install -r requirements.txt && playwright install chromium") from e
        self._pw = sync_playwright().start()
        proxy = {"server": self.cfg.fetch.proxy} if self.cfg.fetch.proxy else None
        try:
            self._browser = self._pw.chromium.launch(
                headless=self.cfg.fetch.headless, proxy=proxy,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        except Exception as e:
            self._pw.stop()
            raise PlaywrightMissing(
                f"Não consegui abrir o Chromium: {e}\n  Rode: playwright install chromium") from e
        self._ctx = self._browser.new_context(
            locale="pt-BR", user_agent=_UA, viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
        self._page = self._ctx.new_page()
        self._page.route("**/*", self._route)
        self._page.on("response", self._on_response)
        return self

    def _route(self, route):
        try:
            if route.request.resource_type in _BLOCK_RESOURCE_TYPES:
                route.abort()
                return
        except Exception:
            pass
        try:
            route.continue_()
        except Exception:
            pass

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    def _on_response(self, resp):
        try:
            req = resp.request
            if "graphql" in resp.url and req.method == "POST":
                self._pending.append(("json", resp))
            elif req.resource_type == "document" and "/ads/library" in resp.url:
                self._pending.append(("html", resp))
        except Exception:
            return

    def _drain(self):
        while self._pending:
            kind, resp = self._pending.pop(0)
            try:
                body = resp.text()
            except Exception:
                continue
            if "ad_archive_id" not in body:
                continue
            if kind == "json":
                for obj in _iter_json_objects(body):
                    self._captured.append(obj)
            else:
                for m in _SCRIPT_JSON.finditer(body):
                    try:
                        self._captured.append(json.loads(m.group(1)))
                    except ValueError:
                        pass

    def _dismiss_cookies(self):
        for lab in _COOKIE_LABELS:
            try:
                btn = self._page.get_by_role("button", name=lab)
                if btn.count():
                    btn.first.click(timeout=2500)
                    self._page.wait_for_timeout(1200)
                    return
            except Exception:
                pass

    def _collect(self, url: str, scrolls: int, label: str) -> list:
        self._pending.clear()
        self._captured.clear()
        self.last_result_count = 0
        try:
            self._page.goto(url, wait_until="commit", timeout=45_000)
        except Exception as e:
            print(f"  ! {label}: falha ao abrir ({e})")
            return []
        self._page.wait_for_timeout(1500)
        if not self._cookies_done:
            self._dismiss_cookies()
            self._cookies_done = True
        self._drain()
        lo, hi = self.cfg.fetch.delay_seconds
        cap = self.cfg.fetch.results_per_keyword_cap * 4
        last, stag = -1, 0
        for _ in range(scrolls):
            try:
                self._page.mouse.wheel(0, 4400)
            except Exception:
                break
            self._page.wait_for_timeout(int(random.uniform(lo, hi) * 1000))
            self._drain()
            cnt = len(self._captured)
            if cnt == last:
                stag += 1
                if stag >= 2:
                    break
            else:
                stag = 0
            last = cnt
            if cnt > cap:
                break
        self.last_result_count = _scan_count(list(self._captured))
        return list(iter_ad_nodes(list(self._captured)))

    def _sleep_between(self):
        time.sleep(random.uniform(0.6, 1.6))

    # ---- API pública ----

    def search_keywords(self, keywords, countries, deadline=None) -> list:
        """[(keyword, country, [nodes]), ...] — cada keyword só nos países da língua dela."""
        from .lang import countries_for
        out = []
        pairs = []
        for k in keywords:
            for c in countries_for(k, countries):
                pairs.append((k, c))

        if self.cfg.fetch.parallel_tabs > 1 and len(pairs) > 1:
            tasks = [((kw, country),
                      _KEYWORD_URL.format(status=self.cfg.active_status,
                                          country=country, q=quote(kw)),
                      self.cfg.fetch.max_scrolls, f"{kw} · {country}")
                     for kw, country in pairs]
            res = collect_many(self.cfg, self.raw_dir, tasks,
                               self.cfg.fetch.parallel_tabs, deadline)
            for kw, country in pairs:
                nodes, _ = res.get((kw, country), ([], 0))
                out.append((kw, country, nodes))
            return out

        for i, (kw, country) in enumerate(pairs):
            if deadline and time.time() > deadline:
                print("  (tempo limite da rodada atingido)")
                break
            label = f"{kw} · {country}"
            url = _KEYWORD_URL.format(status=self.cfg.active_status, country=country,
                                     q=quote(kw))
            nodes = self._collect(url, self.cfg.fetch.max_scrolls, label)
            print(f"  · {label}: {len(nodes)} anúncios")
            if not nodes:
                _dump_empty(self.raw_dir, label, self._captured)
            out.append((kw, country, nodes))
            if i < len(pairs) - 1:
                self._sleep_between()
        return out

    def open_salespage(self, url: str) -> dict | None:
        """Abre a página de vendas do candidato e devolve
        {final_url, html, text}. Usado pelo filtro forte (salespage.py).
        Timeout curto — se não carregar, devolve o que deu ou None."""
        if not url:
            return None
        to = int(getattr(self.cfg.fetch, "salespage_timeout_ms", 9000))
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=to)
        except Exception:
            pass   # pode ter carregado o suficiente mesmo com timeout
        try:
            self._page.wait_for_timeout(1200)
            final_url = self._page.url or url
            html = self._page.content() or ""
            text = self._page.evaluate(
                "() => document.body ? document.body.innerText : ''") or ""
        except Exception:
            return None
        self._pending.clear()
        return {"final_url": final_url, "html": html[:400_000], "text": text[:60_000]}

    def verify_page(self, page_id: str, country: str = "ALL") -> list:
        """Todos os anúncios ativos de uma página (contagem real)."""
        url = _PAGE_URL.format(status="active", country=country, pid=quote(str(page_id)))
        nodes = self._collect(url, self.cfg.fetch.verify_scrolls, f"@{page_id} · {country}")
        self._sleep_between()
        return nodes

    def verify_many(self, items, deadline=None) -> dict:
        """items: [(key, page_id, country), ...] -> {key: ([nodes], count_exato)}.
        Usa as abas paralelas quando parallel_tabs > 1."""
        items = [it for it in items if it[1]]
        if not items:
            return {}
        if self.cfg.fetch.parallel_tabs > 1 and len(items) > 1:
            tasks = [(key, _PAGE_URL.format(status="active", country=country,
                                            pid=quote(str(pid))),
                      self.cfg.fetch.verify_scrolls, f"@{pid} · {country}")
                     for key, pid, country in items]
            return collect_many(self.cfg, self.raw_dir, tasks,
                                self.cfg.fetch.parallel_tabs, deadline)
        out = {}
        for key, pid, country in items:
            nodes = self.verify_page(pid, country)
            out[key] = (nodes, getattr(self, "last_result_count", 0))
        return out


def _dump_empty(raw_dir: Path, label: str, captured) -> None:
    safe = "".join(c if c.isalnum() else "_" for c in label)[:50]
    ts = time.strftime("%Y%m%d-%H%M%S")
    try:
        (raw_dir / f"{ts}__{safe}__EMPTY.json").write_text(
            json.dumps(list(captured)[:40], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
