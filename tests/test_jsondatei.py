from finder.jsondatei import lese_json, schreibe_json


def test_lesen_standard(tmp_path):
    assert lese_json(tmp_path / "fehlt.json", {"x": 1}) == {"x": 1}


def test_schreiben_utf8(tmp_path):
    pfad = tmp_path / "a" / "b.json"
    schreibe_json(pfad, {"n": "Ü"})
    assert pfad.read_text(encoding="utf-8").strip() == '{\n "n": "Ü"\n}'
    assert lese_json(pfad, None) == {"n": "Ü"}
