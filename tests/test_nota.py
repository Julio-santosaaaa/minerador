import json

from minerador import nota

OK = {c: 7 for c in nota.CRITERIOS}


def test_parse_notas_ok():
    assert nota.parse_notas(json.dumps(OK)) == OK


def test_parse_notas_rejects_out_of_range():
    bad = dict(OK, **{"Dor forte": 11})
    assert nota.parse_notas(json.dumps(bad)) is None
    assert nota.parse_notas(json.dumps(dict(OK, **{"Dor forte": 0}))) is None


def test_parse_notas_rejects_missing_key_null_and_garbage():
    assert nota.parse_notas(json.dumps({k: v for k, v in OK.items() if k != "Dor forte"})) is None
    assert nota.parse_notas(json.dumps(dict(OK, **{"Dor forte": None}))) is None
    assert nota.parse_notas("não é json") is None


def test_parse_notas_accepts_fenced_json():
    assert nota.parse_notas("```json\n" + json.dumps(OK) + "\n```") == OK


def test_media_needs_all_six():
    assert nota.media({"Dor forte": 8}) is None
    assert nota.media(None) is None


def test_media_rounds_one_decimal():
    n = dict(OK, **{"Dor forte": 8, "Promessa desejável": 8})
    assert nota.media(n) == 7.3


def _resp(payload):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


def test_avaliar_ok_and_no_key_or_text():
    assert nota.avaliar("x" * 100, "k", "m", post=lambda *a: _resp(OK)) == OK
    assert nota.avaliar("x" * 100, "", "m", post=lambda *a: _resp(OK)) is None
    assert nota.avaliar("   ", "k", "m", post=lambda *a: _resp(OK)) is None


def test_avaliar_retries_once_on_429_then_none():
    calls = []

    def post(*a):
        calls.append(1)
        raise nota.RateLimited()

    assert nota.avaliar("x" * 100, "k", "m", post=post, wait=0) is None
    assert len(calls) == 2
