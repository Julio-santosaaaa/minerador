from minerador.phrases import phrases_from_copies


def test_takes_first_sentence_trimmed_to_words():
    out = phrases_from_copies(["Cansada de gastar sem controle? Baixe agora a planilha completa."])
    assert out == ["cansada de gastar sem controle"]


def test_skips_dynamic_urls_and_short():
    assert phrases_from_copies(["{{product.name}}", "https://x.com/a", "Oi"]) == []


def test_dedupes_and_respects_seen_and_limit():
    copies = ["Planilha pronta para MEI controlar o caixa. x", "planilha pronta para mei controlar o caixa!", "Receitas fit para a semana inteira sem sofrer"]
    out = phrases_from_copies(copies, seen={"receitas fit para a semana inteira sem sofrer"}, limit=5)
    assert out == ["planilha pronta para mei controlar o caixa"]
