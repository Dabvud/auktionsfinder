from finder.normalisieren import vereinheitliche


def test_akzente_und_gross():
    assert vereinheitliche("Víctor IBARBO") == "victor ibarbo"


def test_sz_und_umlaut():
    assert vereinheitliche("Thomas Müller · Größe") == "thomas muller grosse"


def test_satzzeichen():
    assert vereinheitliche("Reus/Haaland-Auto!!") == "reus haaland auto"


def test_leerzeichen():
    assert vereinheitliche("  a   b ") == "a b"
