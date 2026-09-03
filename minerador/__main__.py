from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from . import store
from .config import Config, DB_PATH, RAW_DIR
from .dedupe import build_offers
from .fetch import Miner, PlaywrightMissing
from .parse import parse_nodes
from .score import heat as heat_score, level as heat_level

_COLS = ("Calor", "Nível", "Oferta", "Domínio", "País", "Dias", "Ativos", "Palavra-chave")


def _rows_to_table(rows, title):
    try:
        from rich.console import Console
        from rich.table import Table
        t = Table(title=title)
        for c in _COLS:
            t.add_column(c, overflow="fold")
        for r in rows:
            t.add_row(f"{r['calor']:.1f}", r["nivel"], r["oferta"][:34], r["dominio"][:30],
                      r["pais"][:12], str(r["dias"]), str(r["ativos"]), r["kw"][:32])
        Console().print(t)
    except ImportError:
        print(f"\n{title}")
        for r in rows:
            print(f"  {r['calor']:>4.1f} {r['nivel']:<6} {r['oferta'][:30]:<30} "
                  f"{r['dominio'][:26]:<26} {r['pais']:<10} {r['dias']:>4}d {r['ativos']:>3}")


def _print_picked(picked):
    rows = [{"calor": h, "nivel": lv, "oferta": o.page_name, "dominio": o.domain,
             "pais": ",".join(o.countries), "dias": o.days_active_max, "ativos": o.ad_count,
             "kw": ",".join(o.keywords)} for o, h, lv in picked]
    _rows_to_table(rows, f"{len(picked)} ofertas mineradas nesta rodada")


def _print_db(conn, min_heat, limit):
    src = store.list_offers(conn, min_heat)
    if limit:
        src = src[:limit]
    rows = [{"calor": r["heat"] or 0, "nivel": r["level"] or "🔥",
             "oferta": r["page_name"] or "", "dominio": r["domain"] or "",
             "pais": r["countries"] or "", "dias": r["days_active_max"] or 0,
             "ativos": r["ad_count"] or 0, "kw": r["keywords"] or ""} for r in src]
    _rows_to_table(rows, "Ofertas no SQLite")


def _verify_priority(o) -> int:
    """0 = verificar primeiro (amostra já perto de 10-99)."""
    c = o.ad_count
    if 6 <= c <= 99:
        return 0
    if c > 140:
        return 2          # provável > max_ads
    return 1


def _rows_to_scored(rows, limit=None):
    """linhas de store.list_offers -> [(Offer, heat, level)] pro notion_sync."""
    from .models import Offer
    out = []
    for r in rows:
        o = Offer(page_id=r["page_id"] or "", page_name=r["page_name"] or "",
                  domain=r["domain"] or "", link_url=r["link_url"] or "",
                  ad_count=r["ad_count"] or 0, days_active_max=r["days_active_max"] or 0,
                  collation_total=r["collation_total"] or 0,
                  keywords=[k.strip() for k in (r["keywords"] or "").split(",") if k.strip()],
                  countries=[c for c in (r["countries"] or "").split(",") if c])
        out.append((o, r["heat"] or 1.0, r["level"] or "🔥"))
    return out[:limit] if limit else out


def _recount(ads):
    active = [a for a in ads if a.is_active] or ads
    if not active:
        return 0, 0, 0
    distinct = len({a.ad_archive_id for a in active})
    n = max(distinct, max((a.collation_count for a in active), default=1))
    dmax = max((a.days_active for a in active), default=0)
    ctot = sum(max(a.collation_count, 1) for a in active)
    return n, dmax, ctot


def _dump_reject(offer, data, verdict) -> None:
    """Auditoria: por que o filtro forte rejeitou. Salva motivo + detalhe +
    URL final + trecho do texto da página em data/raw/reject_<ts>_<domínio>.txt."""
    try:
        import time as _t
        safe = "".join(c if c.isalnum() else "_" for c in (offer.domain or "x"))[:40]
        p = RAW_DIR / f"reject_{_t.strftime('%Y%m%d-%H%M%S')}_{safe}.txt"
        body = (
            f"oferta   : {offer.page_name}\n"
            f"domínio  : {offer.domain}\n"
            f"link     : {offer.link_url}\n"
            f"final_url: {data.get('final_url', '')}\n"
            f"motivo   : {verdict.reason}\n"
            f"detalhe  : {verdict.detail}\n"
            f"{'-' * 70}\n"
            f"{(data.get('text') or '')[:8000]}\n"
        )
        p.write_text(body, encoding="utf-8")
    except Exception:
        pass


def _auto_reconcile(cfg, conn) -> None:
    """Reciclagem parte 1: oferta que o Julio apagou no Notion sai do 'synced'
    e volta a poder ser minerada. Silencioso e tolerante a falha de token."""
    if not cfg.notion_token or not cfg.notion_database_id:
        return
    from .recalc import _notion_client, _query_all
    notion = _notion_client(cfg)
    pages = _query_all(notion, cfg.notion_database_id)
    live = {p["id"] for p in pages} | {p["id"].replace("-", "") for p in pages}
    gone = [r["offer_key"] for r in store.all_synced(conn)
            if (r["notion_page_id"] or "").replace("-", "") not in live]
    n = store.forget_synced(conn, gone)
    if n:
        print(f"  reciclagem: {n} oferta(s) apagada(s) do Notion voltaram pro pool")


def _process_pool(m, cfg, conn, kws, cursor, target, deadline, already,
                  picked, picked_keys, all_ads, pool_name) -> int:
    """Roda janelas de `kws` até picked>=target, keywords acabarem ou deadline.
    Cada candidato 9-99 anúncios passa pelo FILTRO FORTE (abre a página de vendas)
    antes de virar 'validado'. Devolve o cursor atualizado."""
    from . import progress
    from .salespage import evaluate
    n_kw = len(kws)
    if not n_kw:
        return cursor
    window = cfg.keyword_window
    max_windows = max(1, (n_kw + window - 1) // window)
    w = 0
    while len(picked) < target and w < max_windows and time.time() < deadline:
        win = [kws[(cursor + i) % n_kw] for i in range(min(window, n_kw))]
        cursor = (cursor + len(win)) % n_kw
        w += 1
        print(f"\n== {pool_name} · janela {w}/{max_windows}: {', '.join(win)} ==")
        progress.set(phase=f"buscando · {pool_name}", janela=f"{w}/{max_windows}",
                     keyword_atual=", ".join(win), validadas=len(picked), target=target)

        ads = []
        for kw, country, nodes in m.search_keywords(win, cfg.countries, deadline):
            ads.extend(parse_nodes(nodes, kw, country))
        all_ads.extend(ads)

        cands = build_offers(ads, ignore_domains=cfg.ignore_domains,
                             infoproduct_only=cfg.infoproduct_only)
        cands = [o for o in cands if o.key not in already
                 and o.key not in picked_keys and o.ad_count >= 2]
        cands.sort(key=lambda o: (_verify_priority(o), -o.days_active_max))
        cap = min(max(target * 2, 16), 32)
        print(f"   {len(cands)} candidatos (verifica contagem de até {cap})")

        window_cands = cands[:cap]
        verify_items = [(o.key, o.page_id,
                         o.countries[0] if o.countries else cfg.countries[0])
                        for o in window_cands if o.page_id]
        vres = m.verify_many(verify_items, deadline) if verify_items else {}

        for o in window_cands:
            if len(picked) >= target or time.time() > deadline:
                break
            if o.key in vres:
                vnodes, exact = vres[o.key]
                vads = parse_nodes(vnodes, "", "")
                all_ads.extend(vads)
                n, dmax, ctot = _recount(vads)
                if exact:
                    n = exact
                if n:
                    o.ad_count = n
                    o.days_active_max = max(o.days_active_max, dmax)
                    o.collation_total = max(o.collation_total, ctot)
            if not (cfg.min_ads <= o.ad_count <= cfg.max_ads):
                continue

            # --- FILTRO FORTE: abre a página de vendas ---
            progress.set(phase="filtro forte · abrindo página",
                         verificando=o.page_name[:44], validadas=len(picked), target=target)
            data = m.open_salespage(o.link_url)
            if not data:
                progress.bump_reject("não abriu a página")
                print(f"   – {o.page_name[:24]:24} {o.domain[:26]:26} — não abriu a página")
                continue
            v = evaluate(o, data, cfg, conn)
            o.price_brl, o.checkout_host = v.price_brl, v.checkout_host
            if not v.ok:
                o.reject_reason = v.reason
                progress.bump_reject(v.reason)
                _dump_reject(o, data, v)
                print(f"   – {o.page_name[:24]:24} {o.domain[:26]:26} — {v.reason}")
                continue

            h = heat_score(o.days_active_max, o.ad_count, o.collation_total,
                           o.started_recently, cfg.heat_weights, cfg.min_days_active)
            lv = heat_level(h)
            picked.append((o, h, lv))
            picked_keys.add(o.key)
            price = f" · R$ {o.price_brl:.0f}" if o.price_brl else ""
            print(f"   ✓ {o.page_name[:24]:24} {o.domain[:26]:26} "
                  f"{o.ad_count:>3} ativos · calor {h}{price}")
            progress.set(validadas=len(picked), target=target)
    return cursor


def cmd_run(args) -> None:
    from . import progress
    cfg = Config.load()
    if args.max_scrolls:
        cfg.fetch.max_scrolls = args.max_scrolls
    if args.window:
        cfg.keyword_window = args.window
    target = args.target if args.target else cfg.daily_target
    deadline_min = args.deadline if args.deadline else cfg.run_deadline_min
    deadline = time.time() + deadline_min * 60
    progress.start(getattr(args, "progress", False))

    principal = [args.keyword] if args.keyword else cfg.keywords
    reserve = [] if args.keyword else cfg.keywords_reserve
    if not principal:
        sys.exit("Nenhuma palavra-chave em config.yaml.")

    print(f"Minerador v6 — países={','.join(cfg.countries)} · anúncios "
          f"{cfg.min_ads}-{cfg.max_ads} · teto R$ {cfg.price_ceiling_brl:.0f} · "
          f"alvo={target} validadas · reciclagem {cfg.recycle_days}d · "
          f"deadline {deadline_min}min")

    conn = store.connect(DB_PATH)
    try:
        _auto_reconcile(cfg, conn)
    except Exception as e:
        print(f"  (reconcile pulado: {e})")
    already = store.synced_keys(conn, exclude_stale_days=cfg.recycle_days)
    run_id = store.start_run(conn, principal)
    cursor = int(store.kv_get(conn, "kw_cursor", "0") or 0)

    picked, picked_keys, all_ads = [], set(), []
    try:
        with Miner(cfg, RAW_DIR) as m:
            cursor = _process_pool(m, cfg, conn, principal, cursor, target, deadline,
                                   already, picked, picked_keys, all_ads, "principal")
            store.kv_set(conn, "kw_cursor", cursor)
            if len(picked) < target and reserve and time.time() < deadline:
                print(f"\n>> principal deu {len(picked)}/{target} validadas — "
                      f"abrindo o pool RESERVA ({len(reserve)} keywords)")
                progress.set(phase="pool reserva")
                _process_pool(m, cfg, conn, reserve, 0, target, deadline,
                              already, picked, picked_keys, all_ads, "reserva")
    except PlaywrightMissing as e:
        sys.exit(str(e))

    store.save_ads(conn, run_id, all_ads)
    picked.sort(key=lambda x: x[1], reverse=True)
    for o, h, lv in picked:
        store.upsert_offer(conn, o, h, lv)
    store.finish_run(conn, run_id, len(all_ads), len(picked))

    print()
    _print_picked(picked)

    if len(picked) < target:
        print(f"\n⚠️ BIBLIOTECA SECA: {len(picked)}/{target} validadas nesta rodada "
              f"(varri principal + reserva). Sobe o que tem; rode de novo mais tarde.")
    progress.finish({"validadas": len(picked), "target": target})

    # o que vai pro Notion: TOP `sync_target` do SQLite = novas desta rodada
    # (já upsertadas acima) + backlog de rodadas anteriores que ainda não subiu.
    n_sync = args.sync_target if args.sync_target else cfg.sync_target
    to_sync = _rows_to_scored(store.list_offers(conn, 0.0), limit=n_sync)

    if args.dry_run:
        print(f"\n[dry-run] {len(picked)} novas no SQLite · {len(to_sync)} prontas pro "
              f"Notion (nada enviado).")
        return
    if not to_sync:
        print("\nNada pra enviar ao Notion.")
        return
    if len(picked) < target and len(to_sync) > len(picked):
        print(f"\nCompletando o Notion com o backlog de validadas de rodadas anteriores "
              f"({len(to_sync) - len(picked)}).")
    from .notion_sync import sync
    try:
        res = sync(conn, to_sync, cfg)
    except RuntimeError as e:
        sys.exit(f"\nNotion: {e}\n(as ofertas estão salvas no SQLite — depois de arrumar o "
                 f"token/conexão, rode: scripts/run.sh sync)")
    print(f"\nNotion: +{res['created']} novas, ~{res['updated']} atualizadas, {res['failed']} falhas "
          f"({len(to_sync)} enviadas)")


def cmd_list(args) -> None:
    conn = store.connect(DB_PATH)
    _print_db(conn, args.min_heat, args.top)


def cmd_export(args) -> None:
    conn = store.connect(DB_PATH)
    rows = store.list_offers(conn, 0.0)
    out = Path(args.path)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys() if rows else ["offer_key"])
        for r in rows:
            writer.writerow(list(r))
    print(f"{len(rows)} ofertas -> {out}")


def cmd_sync(args) -> None:
    cfg = Config.load()
    conn = store.connect(DB_PATH)
    rows = store.list_offers(conn, args.min_heat)
    if not rows:
        sys.exit("Nada no SQLite. Rode `minerador run` antes.")
    limit = args.sync_target if getattr(args, "sync_target", None) else cfg.sync_target
    scored = _rows_to_scored(rows, limit=limit)
    from .notion_sync import sync
    try:
        res = sync(conn, scored, cfg)
    except RuntimeError as e:
        sys.exit(f"Notion: {e}")
    print(f"Notion: +{res['created']} novas, ~{res['updated']} atualizadas, {res['failed']} falhas")


def cmd_recalc(args) -> None:
    from .recalc import cmd_recalc as _run
    _run(args)


def cmd_reconcile(args) -> None:
    from .recalc import cmd_reconcile as _run
    _run(args)


def cmd_setup_notion(args) -> None:
    from .notion_setup import create_database
    create_database()


def cmd_notion_trim(args) -> None:
    from .notion_setup import trim_database
    trim_database()


def cmd_notion_clear(args) -> None:
    from .notion_setup import clear_database
    clear_database()


def cmd_prune(args) -> None:
    """Enxuga o SQLite: guarda só os anúncios das últimas N rodadas + VACUUM.
    Roda no fim do job de nuvem pra o banco commitado não inchar."""
    import sqlite3
    keep = args.keep if getattr(args, "keep", None) else 3
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM ads WHERE run_id NOT IN "
                 "(SELECT id FROM runs ORDER BY id DESC LIMIT ?)", (keep,))
    conn.execute("DELETE FROM runs WHERE id NOT IN "
                 "(SELECT id FROM runs ORDER BY id DESC LIMIT ?)", (keep,))
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    mb = DB_PATH.stat().st_size / 1e6
    print(f"prune: mantidas {keep} rodadas · banco agora {mb:.1f} MB")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="minerador")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="minera N ofertas novas -> SQLite + Notion")
    r.add_argument("--keyword", help="só esta palavra-chave (ignora a rotação)")
    r.add_argument("--target", type=int, help="quantas ofertas novas (default: config.daily_target)")
    r.add_argument("--sync-target", type=int, dest="sync_target",
                   help="quantas ofertas mandar pro Notion (novas + backlog; default: config.sync_target)")
    r.add_argument("--window", type=int, help="palavras-chave por janela")
    r.add_argument("--deadline", type=int, help="tempo limite da rodada em minutos")
    r.add_argument("--max-scrolls", type=int)
    r.add_argument("--dry-run", action="store_true", help="não escreve no Notion")
    r.add_argument("--progress", action="store_true",
                   help="escreve data/progress.json a cada evento (acompanhamento ao vivo)")
    r.set_defaults(func=cmd_run)

    l = sub.add_parser("list", help="lista as ofertas do SQLite")
    l.add_argument("--min-heat", type=float, default=0.0)
    l.add_argument("--top", type=int, default=0)
    l.set_defaults(func=cmd_list)

    e = sub.add_parser("export", help="exporta CSV")
    e.add_argument("path")
    e.set_defaults(func=cmd_export)

    y = sub.add_parser("sync", help="empurra o SQLite pro Notion sem minerar")
    y.add_argument("--min-heat", type=float, default=0.0)
    y.add_argument("--sync-target", type=int, dest="sync_target",
                   help="quantas ofertas mandar (default: config.sync_target)")
    y.set_defaults(func=cmd_sync)

    rc = sub.add_parser("recalc",
                        help="recalcula anúncios/dias das ofertas que já estão no Notion "
                             "+ grava o snapshot do dia (tracker de progresso)")
    rc.add_argument("--scrolls", type=int, help="scrolls por oferta (default: config.recalc_scrolls)")
    rc.set_defaults(func=cmd_recalc)

    rco = sub.add_parser("reconcile",
                         help="sincroniza o SQLite com o Notion: ofertas que você apagou "
                              "no Notion voltam a poder ser mineradas (backfill até 20)")
    rco.set_defaults(func=cmd_reconcile)

    s = sub.add_parser("setup-notion", help="cria o banco no Notion")
    s.set_defaults(func=cmd_setup_notion)

    nt = sub.add_parser("notion-trim",
                        help="remove as colunas CALOR / CÓPIAS DO CRIATIVO / NÍVEL do banco no Notion")
    nt.set_defaults(func=cmd_notion_trim)

    nc = sub.add_parser("notion-clear",
                        help="arquiva TODAS as ofertas do banco no Notion e zera o rastro no SQLite")
    nc.set_defaults(func=cmd_notion_clear)

    pr = sub.add_parser("prune", help="enxuga o SQLite (só as últimas N rodadas) + VACUUM")
    pr.add_argument("--keep", type=int, help="quantas rodadas manter (default 3)")
    pr.set_defaults(func=cmd_prune)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
