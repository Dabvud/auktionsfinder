from copy import deepcopy

import pytest

from finder.archiv import archiviere, einpflegen


def test_neu(auktion_fabrik, jetzt):
    auktion = auktion_fabrik()
    spaeter = auktion_fabrik("v1|100000000002|0", ende="2026-11-08T12:00:00Z")
    laufend, beendet, neu = einpflegen([], [spaeter, auktion], jetzt)
    assert laufend == [auktion, spaeter]
    assert beendet == []
    assert neu == 2
    assert einpflegen([], [auktion], jetzt) == ([auktion], [], 1)


def test_bekannt_aktualisiert(auktion_fabrik, jetzt):
    alt = auktion_fabrik(zuerst_gesehen="2026-11-05T12:00:00Z", zuletzt_gesehen="2026-11-05T12:00:00Z")
    treffer = auktion_fabrik(preis_cent=1750, gebote=5, spieler=["erling-haaland"], vereine=["manchester-city"], typen=["relic"])
    laufend, beendet, neu = einpflegen([alt], [treffer], jetzt)
    assert laufend == [{**treffer, "zuerst_gesehen": "2026-11-05T12:00:00Z",
                        "spieler": ["erling-haaland", "marco-reus"], "vereine": ["bvb", "manchester-city"],
                        "typen": ["auto", "relic"]}]
    assert beendet == []
    assert neu == 0


def test_doppelt_im_lauf(auktion_fabrik, jetzt):
    auto = auktion_fabrik()
    relic = auktion_fabrik(typen=["relic"])
    laufend, beendet, neu = einpflegen([], [auto, relic, auto], jetzt)
    assert laufend == [{**auto, "typen": ["auto", "relic"]}]
    assert beendet == []
    assert neu == 1


@pytest.mark.parametrize("ende", ["2026-11-07T12:00:00Z", "2026-11-06T12:00:00Z"])
def test_fehlt_aber_nicht_beendet(auktion_fabrik, jetzt, ende):
    alt = auktion_fabrik(ende=ende, zuletzt_gesehen="2026-11-05T12:00:00Z")
    vorher = deepcopy(alt)
    assert einpflegen([alt], [], jetzt) == ([vorher], [], 0)


def test_beendet_nach_endzeit(auktion_fabrik, jetzt):
    alt = auktion_fabrik(ende="2026-11-06T11:59:59Z", preis_cent=2350)
    laufend, beendet, neu = einpflegen([alt], [], jetzt)
    assert laufend == []
    assert beendet == [{**alt, "status": "beendet", "endpreis_cent": 2350}]
    assert neu == 0


def test_archiv_monat(tmp_path, auktion_fabrik, json_lesen):
    november = auktion_fabrik(ende="2026-11-30T23:00:00Z", status="beendet", endpreis_cent=1250)
    oktober = auktion_fabrik("v1|100000000002|0", ende="2026-10-31T23:00:00Z", status="beendet", endpreis_cent=1250)
    archiv = tmp_path / "archiv"
    archiviere([november, oktober], archiv)
    assert json_lesen(archiv / "2026-11.json") == {"auktionen": [november]}
    assert json_lesen(archiv / "2026-10.json") == {"auktionen": [oktober]}
    assert json_lesen(archiv / "index.json") == {"monate": ["2026-11", "2026-10"]}


def test_archiv_ohne_duplikat(tmp_path, auktion_fabrik, json_lesen):
    auktion = auktion_fabrik(status="beendet", endpreis_cent=1250)
    archiviere([auktion, auktion], tmp_path)
    archiviere([auktion], tmp_path)
    assert json_lesen(tmp_path / "2026-11.json") == {"auktionen": [auktion]}
    assert json_lesen(tmp_path / "index.json") == {"monate": ["2026-11"]}


def test_archiv_behaelt_alte(tmp_path, auktion_fabrik, json_lesen, json_schreiben):
    alt = auktion_fabrik(status="beendet", endpreis_cent=1250)
    neu = auktion_fabrik("v1|100000000002|0", status="beendet", endpreis_cent=2000)
    oktober = auktion_fabrik("v1|100000000003|0", ende="2026-10-15T12:00:00Z", status="beendet", endpreis_cent=99)
    json_schreiben(tmp_path / "2026-11.json", {"auktionen": [alt]})
    json_schreiben(tmp_path / "2026-10.json", {"auktionen": [oktober]})
    json_schreiben(tmp_path / "index.json", {"monate": ["2026-11", "2026-10"]})
    oktober_bytes = (tmp_path / "2026-10.json").read_bytes()
    archiviere([neu], tmp_path)
    assert sorted(json_lesen(tmp_path / "2026-11.json")["auktionen"], key=lambda a: a["item_id"]) == [alt, neu]
    assert (tmp_path / "2026-10.json").read_bytes() == oktober_bytes
    assert json_lesen(tmp_path / "index.json") == {"monate": ["2026-11", "2026-10"]}
