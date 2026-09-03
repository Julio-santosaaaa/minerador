"""Status ao vivo da rodada (para acompanhamento no chat/terminal).

`minerador run --progress` liga a escrita de data/progress.json a cada evento:
fase, janela X/Y, keyword atual, candidatos, validadas, rejeitadas + motivo,
tempo decorrido e ETA. Custo ~zero. Sem a flag, não escreve nada.
"""
from __future__ import annotations

import json
import time

from .config import DATA_DIR

_S = {"on": False, "start": 0.0, "path": DATA_DIR / "progress.json", "data": {}}


def start(enabled: bool) -> None:
    _S["on"] = bool(enabled)
    _S["start"] = time.time()
    _S["data"] = {"phase": "iniciando", "validadas": 0, "rejeitadas": 0,
                  "rejeitadas_motivos": []}
    _flush()


def set(**kw) -> None:
    if not _S["on"]:
        return
    _S["data"].update(kw)
    _flush()


def bump_reject(reason: str) -> None:
    if not _S["on"]:
        return
    _S["data"]["rejeitadas"] = _S["data"].get("rejeitadas", 0) + 1
    lst = _S["data"].setdefault("rejeitadas_motivos", [])
    lst.append(reason)
    _S["data"]["rejeitadas_motivos"] = lst[-12:]
    _flush()


def _flush() -> None:
    if not _S["on"]:
        return
    elapsed = int(time.time() - _S["start"])
    out = {"elapsed_s": elapsed, "elapsed": f"{elapsed // 60}min{elapsed % 60:02d}s"}
    v = _S["data"].get("validadas", 0)
    target = _S["data"].get("target", 20)
    if v and elapsed > 30 and v < target:
        eta = int(elapsed / v * (target - v))
        out["eta"] = f"~{eta // 60}min"
    out.update(_S["data"])
    try:
        _S["path"].parent.mkdir(parents=True, exist_ok=True)
        _S["path"].write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    except Exception:
        pass


def finish(summary: dict) -> None:
    if not _S["on"]:
        return
    _S["data"].update(summary)
    _S["data"]["phase"] = "concluída"
    _flush()
