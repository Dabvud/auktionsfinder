from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from finder.spieler import baue_index
from finder.suchplan import Suche, oder_gruppen, plane_suchen


def gespeichert(**filterwerte):
    return {"id": "test", "name": "Testsuche", "filter": {
        "typ": "alle", "verein": None, "liga": None, "spieler": None,
        "gruppe": None, "max_preis": None, **filterwerte,
    }}


def test_oder_gruppen_grenze():
    namen = [f"nachname{nr:02d}" for nr in range(30)]
    gruppen = oder_gruppen(namen)
    assert all(gruppe.startswith("(") and gruppe.endswith(")") for gruppe in gruppen)
    assert all(len(gruppe) <= 100 for gruppe in gruppen)
    assert [name for gruppe in gruppen for name in gruppe[1:-1].split(", ")] == namen
    # Eine kleinere Grenze muss ebenfalls eingehalten werden.
    assert oder_gruppen(["reus", "haaland", "ibarbo"], max_len=15) == ["(reus, haaland)", "(ibarbo)"]


def test_plan_typen(kartentypen, vereine, spieler_daten):
    plan = plane_suchen(kartentypen, {"suchen": []}, baue_index(spieler_daten), vereine)
    erwartet = [
        ("(auto, autograph, signed, signature, signiert, autogramm)", "auto"),
        ("(relic, patch, jersey, memorabilia, game worn, worn, trikot)", "relic"),
        ("numbered", "nummeriert"), ("nummeriert", "nummeriert"), ("(rookie, rc)", "rookie"),
    ]
    assert len(plan) == 10
    assert {(suche.q, suche.typ, suche.aspekt) for suche in plan} == {
        (q, typ, aspekt) for q, typ in erwartet for aspekt in (True, False)
    }
    assert all(isinstance(suche, Suche) for suche in plan)
    assert is_dataclass(Suche) == True
    with pytest.raises(FrozenInstanceError):
        plan[0].q = "verändert"


@pytest.mark.parametrize(("filterwerte", "namen"), [
    ({"verein": "bvb"}, ["haaland", "reus"]),
    ({"spieler": "marco-reus"}, ["reus"]),
    ({"gruppe": "fifa-kult"}, ["haaland"]),
])
def test_plan_alle_karten(kartentypen, vereine, spieler_daten, filterwerte, namen):
    plan = plane_suchen(kartentypen, {"suchen": [gespeichert(**filterwerte)]}, baue_index(spieler_daten), vereine)
    alle = [suche for suche in plan if suche.typ == "alle"]
    assert len(alle) == 2
    assert {suche.aspekt for suche in alle} == {True, False}
    for suche in alle:
        assert sorted(suche.q[1:-1].split(", ")) == namen
        assert len(suche.q) <= 100


def test_plan_alle_ohne_auswahl(kartentypen, vereine, spieler_daten):
    plan = plane_suchen(kartentypen, {"suchen": [gespeichert()]}, baue_index(spieler_daten), vereine)
    assert len(plan) == 10
    assert [suche for suche in plan if suche.typ == "alle"] == []


def test_plan_ohne_doppelte(kartentypen, vereine, spieler_daten):
    erste = gespeichert(verein="bvb")
    zweite = {**gespeichert(verein="bvb"), "id": "zweite", "name": "Noch einmal BVB"}
    plan = plane_suchen(kartentypen, {"suchen": [erste, zweite]}, baue_index(spieler_daten), vereine)
    assert len(plan) == 12
    alle = [suche for suche in plan if suche.typ == "alle"]
    assert len(alle) == 2
    assert {suche.aspekt for suche in alle} == {True, False}
    assert [sorted(suche.q[1:-1].split(", ")) for suche in alle] == [["haaland", "reus"], ["haaland", "reus"]]


def test_plan_ueberspringt_unbrauchbare_namen(kartentypen, vereine, spieler_fabrik):
    daten = {"spieler": [spieler_fabrik("leer", "!!!", gruppen=["favorit"]),
                         spieler_fabrik("lang", "x" + "y" * 120, gruppen=["favorit"]),
                         spieler_fabrik("ibarbo", "Ibarbo", gruppen=["favorit"])]}
    plan = plane_suchen(kartentypen, {"suchen": [gespeichert(gruppe="favorit")]}, baue_index(daten), vereine)
    assert {suche.q for suche in plan if suche.typ == "alle"} == {"(ibarbo)"}
