import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from minerador.config import Config
from minerador.fetch import Miner
from minerador.parse import parse_nodes

OFFERS = [
    ("HELP GLOBAL BRAZIL",        "908970792304895",  "BR", 13, 48),
    ("TALITA PEROSA NUTRI",       "106253239248296",  "BR", 40, 93),
    ("THIAGOLOBOS.OFC",           "139278955925282",  "BR", 40, 108),
    ("HASHTAG TREINAMENTOS",      "575394769275332",  "BR", 40, 577),
    ("CANVA DESCOMPLICADO",       "288961070977028",  "BR", 11, 620),
    ("ENERGIA RENTABLE",          "656438854200927",  "ES", 30, 70),
    ("METODO PESO IDEAL",         "770689772790992",  "ES", 18, 88),
    ("BRASIL PARALELO",           "301774903545521",  "BR", 40, 251),
    ("MATHEUS O. SILVA PSIC",     "1501955649935158", "BR", 30, 691),
    ("AMERICAN COACHING ACADEMY", "1548441432113194", "US", 39, 1096),
    ("SHELBY SAPP",               "293210107207936",  "US", 30, 209),
    ("FABIANA BERTOTTI",          "314817081938879",  "BR", 40, 234),
    ("AUTOR LEONARDO GOULART",    "877095975493290",  "BR", 40, 203),
    ("CURSOS ECOM",               "922247398167708",  "ES", 40, 308),
]

cfg = Config.load(Path(__file__).resolve().parents[1] / "config.yaml")
cfg.fetch.verify_scrolls = 12
raw = Path(__file__).resolve().parents[1] / "data" / "raw"

rows = []
with Miner(cfg, raw) as m:
    for name, pid, country, n_notion, d_notion in OFFERS:
        try:
            nodes = m.verify_page(pid, country)
            ads = parse_nodes(nodes, "", country)
            active = [a for a in ads if a.is_active]
            distinct = len({a.ad_archive_id for a in active})
            n = max(distinct, max((a.collation_count for a in active), default=0))
            dmax = max((a.days_active for a in active), default=0)
        except Exception as e:
            n, dmax, distinct = -1, -1, -1
            print(f"ERRO {name}: {e}")
        row = dict(name=name, pid=pid, country=country,
                   n_notion=n_notion, n_real=n, distinct=distinct,
                   d_notion=d_notion, d_real=dmax)
        rows.append(row)
        print(f"{name:28} notion={n_notion:>3} real={n:>3} (distintos {distinct:>3}) | "
              f"dias notion={d_notion:>4} real={dmax:>4}")

(Path(__file__).resolve().parents[1] / "data" / "verify_offers.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
