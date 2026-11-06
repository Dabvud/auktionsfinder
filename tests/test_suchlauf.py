from datetime import datetime, timezone
import json
import sys

import pytest

from finder.ebay import EbayFehler
import finder.suchlauf as suchlauf_modul
from finder.suchlauf import suchlauf


def test_lauf_schreibt_laufend_und_status(daten_ordner, fake_client, fixture_json, json_lesen, jetzt):
    treffer = fixture_json("ebay_seite1.json")["itemSummaries"] + fixture_json("ebay_seite2.json")["itemSummaries"]
    client = fake_client(lambda q, aspekt: treffer)
    client.warnungen = ["Preisband abgeschnitten"]
    status = suchlauf(daten_ordner, client, jetzt)
    auktionen = json_lesen(daten_ordner / "laufend.json")["auktionen"]
    assert len(auktionen) == 3
    assert {a["item_id"]: a["spieler"] for a in auktionen} == {
        "v1|100000000001|0": ["marco-reus"],
        "v1|100000000002|0": ["erling-haaland"], "v1|100000000003|0": [],
    }
    assert all(a["status"] == "laufend" for a in auktionen)
    zeilen = [json.dumps(a, ensure_ascii=False, separators=(",", ":")) for a in auktionen]
    assert (daten_ordner / "laufend.json").read_bytes() == (
        '{"auktionen": [\n' + ",\n".join(zeilen) + "\n]}\n"
    ).encode("utf-8")
    assert status["start"] == jetzt
    assert status["ok"] == True
    assert status["fehler"] == None
    assert status["gefunden"] == 3
    assert status["neu"] == 3
    assert status["beendet"] == 0
    assert status["abfragen"] == 10
    assert status["warnungen"] == ["Preisband abgeschnitten"]
    assert json_lesen(daten_ordner / "status.json") == status
    assert set(status) == {"start", "ende", "ok", "fehler", "gefunden", "neu", "beendet", "abfragen", "warnungen"}
    assert status["ende"].endswith("Z") == True
    assert datetime.fromisoformat(status["ende"].replace("Z", "+00:00")).tzinfo == timezone.utc
    assert len(client.aufrufe) == 10


def test_lauf_archiviert_beendete(daten_ordner, fake_client, auktion_fabrik, json_schreiben, json_lesen, jetzt):
    alt = auktion_fabrik(ende="2026-10-31T23:00:00Z", preis_cent=2350)
    json_schreiben(daten_ordner / "laufend.json", {"auktionen": [alt]})
    status = suchlauf(daten_ordner, fake_client(), jetzt)
    assert json_lesen(daten_ordner / "laufend.json") == {"auktionen": []}
    assert json_lesen(daten_ordner / "archiv/2026-10-31.json") == {
        "auktionen": [{**alt, "status": "beendet", "endpreis_cent": 2350}],
    }
    assert json_lesen(daten_ordner / "archiv/index.json") == {"tage": ["2026-10-31"]}
    assert status["beendet"] == 1
    assert status["neu"] == 0
    assert status["ok"] == True


def test_fehler_laesst_daten_unveraendert(
    daten_ordner, fake_client, fixture_json, auktion_fabrik, json_schreiben, json_lesen, jetzt, monkeypatch,
):
    alt = auktion_fabrik(ende="2026-10-31T23:00:00Z")
    json_schreiben(daten_ordner / "laufend.json", {"auktionen": [alt]})
    json_schreiben(daten_ordner / "archiv/2026-09-30.json", {"auktionen": [
        auktion_fabrik("v1|100000000099|0", status="beendet", ende="2026-09-30T23:00:00Z", endpreis_cent=1250),
    ]})
    json_schreiben(daten_ordner / "archiv/index.json", {"tage": ["2026-09-30"]})
    vorher = {pfad.relative_to(daten_ordner): pfad.read_bytes() for pfad in daten_ordner.rglob("*.json")}

    def erstelle_client(*args, **kwargs):
        client = fake_client()

        def antwort(q, aspekt):
            if client.abfragen == 2:
                raise EbayFehler("HTTP 500 auf Seite 3")
            return fixture_json("ebay_seite1.json")["itemSummaries"]

        client.antwort = antwort
        return client

    status = suchlauf(daten_ordner, erstelle_client(), jetzt)
    assert status["ok"] == False
    assert "HTTP 500 auf Seite 3" in status["fehler"]
    assert status["abfragen"] == 2
    assert json_lesen(daten_ordner / "status.json") == status
    assert {p.relative_to(daten_ordner): p.read_bytes() for p in daten_ordner.rglob("*.json")
            if p.name != "status.json"} == vorher
    monkeypatch.setenv("EBAY_CLIENT_ID", "test-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(suchlauf_modul, "EbayClient", erstelle_client)
    monkeypatch.setattr(sys, "argv", ["finder.suchlauf", "--daten", str(daten_ordner)])
    assert suchlauf_modul.main() == 1
    status = json_lesen(daten_ordner / "status.json")
    assert status["ok"] == False
    assert "HTTP 500 auf Seite 3" in status["fehler"]
    assert {p.relative_to(daten_ordner): p.read_bytes() for p in daten_ordner.rglob("*.json")
            if p.name != "status.json"} == vorher


@pytest.mark.parametrize("fehlend", ["EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"])
def test_fehlende_secrets(daten_ordner, json_lesen, monkeypatch, fehlend):
    monkeypatch.setenv("EBAY_CLIENT_ID", "test-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "test-secret")
    monkeypatch.delenv(fehlend)
    monkeypatch.setattr(sys, "argv", ["finder.suchlauf", "--daten", str(daten_ordner)])
    assert suchlauf_modul.main() == 1
    status = json_lesen(daten_ordner / "status.json")
    assert status["ok"] == False
    assert status["fehler"] == "eBay-Schlüssel fehlt"


@pytest.mark.parametrize(("aspekt", "anzahl"), [(False, 0), (True, 1)])
def test_b_ohne_bezug_verworfen(daten_ordner, fake_client, fixture_json, json_lesen, jetzt, aspekt, anzahl):
    item = fixture_json("ebay_seite1.json")["itemSummaries"][0]
    item["title"] = "Topps Basketball Unbekannt Auto"
    client = fake_client(lambda q, a: [item] if a == aspekt else [])
    status = suchlauf(daten_ordner, client, jetzt)
    auktionen = json_lesen(daten_ordner / "laufend.json")["auktionen"]
    assert len(auktionen) == anzahl
    assert status["neu"] == anzahl
    assert [a["item_id"] for a in auktionen] == (["v1|100000000001|0"] if aspekt else [])


def test_b_mit_spieler_behalten(daten_ordner, fake_client, fixture_json, json_lesen, jetzt):
    item = fixture_json("ebay_seite1.json")["itemSummaries"][0]
    client = fake_client(lambda q, aspekt: [] if aspekt else [item])
    status = suchlauf(daten_ordner, client, jetzt)
    auktionen = json_lesen(daten_ordner / "laufend.json")["auktionen"]
    assert len(auktionen) == 1
    assert auktionen[0]["spieler"] == ["marco-reus"]
    assert auktionen[0]["item_id"] == "v1|100000000001|0"
    assert status["neu"] == 1


def test_main_kuerzt_zeitstempel(daten_ordner, fake_client, fixture_json, json_lesen, monkeypatch):
    class FesteZeit(datetime):
        @classmethod
        def now(cls, tz):
            return cls(2026, 11, 6, 9, 16, 1, 987654, tzinfo=tz)

    monkeypatch.setattr(suchlauf_modul, "datetime", FesteZeit)
    monkeypatch.setenv("EBAY_CLIENT_ID", "test-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(sys, "argv", ["finder.suchlauf", "--daten", str(daten_ordner)])
    item = fixture_json("ebay_echt_beispiel.json")["itemSummaries"][1]
    monkeypatch.setattr(suchlauf_modul, "EbayClient", lambda *args: fake_client(lambda q, aspekt: [item]))
    assert suchlauf_modul.main() == 0
    auktion = json_lesen(daten_ordner / "laufend.json")["auktionen"][0]
    assert auktion["zuerst_gesehen"] == auktion["zuletzt_gesehen"] == "2026-11-06T09:16:01Z"
    assert auktion["ende"] == item["itemEndDate"]


@pytest.mark.parametrize(("titel", "erwartete_vereine"), [
    ("BVB Unbekannt Auto", ["bvb"]), ("UEFA Champions League Unbekannt Auto", []),
])
def test_b_mit_fussball_oder_verein_behalten(
    daten_ordner, fake_client, fixture_json, json_lesen, jetzt, titel, erwartete_vereine,
):
    item = fixture_json("ebay_seite1.json")["itemSummaries"][0]
    item["title"] = titel
    status = suchlauf(daten_ordner, fake_client(lambda q, aspekt: [] if aspekt else [item]), jetzt)
    auktionen = json_lesen(daten_ordner / "laufend.json")["auktionen"]
    assert len(auktionen) == 1
    assert auktionen[0]["spieler"] == []
    assert auktionen[0]["vereine"] == erwartete_vereine
    assert status["neu"] == 1


def test_favoriten_werden_angelegt_und_gesucht(daten_ordner, fake_client, json_schreiben, json_lesen, jetzt):
    json_schreiben(daten_ordner / "favoriten.json", {"namen": ["Víctor Ibarbo", "Marco Reus"]})
    client = fake_client()
    status = suchlauf(daten_ordner, client, jetzt)
    assert status["ok"] == True
    spieler = {s["id"]: s for s in json_lesen(daten_ordner / "spieler.json")["spieler"]}
    assert spieler["victor-ibarbo"]["gruppen"] == ["favorit"]
    assert "favorit" in spieler["marco-reus"]["gruppen"]
    assert {(q, aspekt) for q, aspekt in client.aufrufe if q == "(ibarbo, reus)"} == {
        ("(ibarbo, reus)", True), ("(ibarbo, reus)", False)}


def test_ohne_favoriten_bleibt_spieler_json_unberuehrt(daten_ordner, fake_client, jetzt):
    vorher = (daten_ordner / "spieler.json").read_bytes()
    suchlauf(daten_ordner, fake_client(), jetzt)
    assert (daten_ordner / "spieler.json").read_bytes() == vorher
