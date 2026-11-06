import pytest

from finder import jsondatei
from finder.jsondatei import lese_json, schreibe_json


def test_lesen_standard(tmp_path):
    assert lese_json(tmp_path / "fehlt.json", {"x": 1}) == {"x": 1}


def test_schreiben_utf8(tmp_path):
    pfad = tmp_path / "a" / "b.json"
    schreibe_json(pfad, {"n": "Ü"})
    assert pfad.read_text(encoding="utf-8").strip() == '{\n "n": "Ü"\n}'
    assert lese_json(pfad, None) == {"n": "Ü"}


@pytest.mark.parametrize(("auktionen", "inhalt"), [
    ([], '{"auktionen": [\n\n]}\n'),
    ([{"titel": 'Ü\n"Auto"', "preis_cent": 123, "bild": None}, {"gebote": 0}],
     '{"auktionen": [\n{"titel":"Ü\\n\\"Auto\\"","preis_cent":123,"bild":null},\n{"gebote":0}\n]}\n'),
])
def test_schreibe_auktionen_format(tmp_path, auktionen, inhalt):
    pfad = tmp_path / "daten" / "laufend.json"
    jsondatei.schreibe_auktionen(pfad, auktionen)
    assert pfad.read_bytes() == inhalt.encode("utf-8")
    assert lese_json(pfad, None) == {"auktionen": auktionen}


def test_schreibe_auktionen_atomare_ersetzung(tmp_path, monkeypatch):
    pfad = tmp_path / "laufend.json"
    vorher = b'{"auktionen": []}\n'
    pfad.write_bytes(vorher)
    ersetzen = jsondatei.os.replace

    def pruefe_ersetzung(quelle, ziel):
        assert ziel == pfad
        assert quelle.parent == pfad.parent
        assert pfad.read_bytes() == vorher
        assert lese_json(quelle, None) == {"auktionen": [{"titel": "Neu"}]}
        ersetzen(quelle, ziel)

    monkeypatch.setattr(jsondatei.os, "replace", pruefe_ersetzung)
    jsondatei.schreibe_auktionen(pfad, [{"titel": "Neu"}])
    assert lese_json(pfad, None) == {"auktionen": [{"titel": "Neu"}]}
    assert list(tmp_path.iterdir()) == [pfad]


def test_schreibe_auktionen_fehler_erhaelt_datei(tmp_path):
    pfad = tmp_path / "laufend.json"
    vorher = b'{"auktionen": []}\n'
    pfad.write_bytes(vorher)
    with pytest.raises(TypeError):
        jsondatei.schreibe_auktionen(pfad, [{"titel": "Neu"}, {"ungueltig": object()}])
    assert pfad.read_bytes() == vorher
    assert list(tmp_path.iterdir()) == [pfad]
