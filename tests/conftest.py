"""Lokale Testdaten und Fakes; keine Imports aus dem künftigen Produktcode."""

from copy import deepcopy
import json
from pathlib import Path
import socket
import urllib.request
from urllib.parse import parse_qs, urlsplit

import pytest


WURZEL = Path(__file__).resolve().parents[1]
JETZT = "2026-11-06T12:00:00Z"


def lies(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


def schreibe(pfad, daten):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


class FakeHttp:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def __call__(self, methode, url, header, body):
        self.aufrufe.append((methode, url, deepcopy(header), body))
        if url == "https://api.ebay.com/identity/v1/oauth2/token":
            return {"access_token": "t", "expires_in": 7200}
        return deepcopy(self.antwort(methode, url, header, body))

    @property
    def suchen(self):
        return [aufruf for aufruf in self.aufrufe if urlsplit(aufruf[1]).path.endswith("/item_summary/search")]


class FakeEbayClient:
    def __init__(self, antwort=None, warnungen=()):
        self.antwort = antwort or (lambda q, aspekt: [])
        self.warnungen = list(warnungen)
        self.abfragen = 0
        self.aufrufe = []

    def suche(self, q, aspekt):
        self.abfragen += 1
        self.aufrufe.append((q, aspekt))
        return deepcopy(self.antwort(q, aspekt))


@pytest.fixture(autouse=True)
def kein_netz(monkeypatch):
    def verboten(*args, **kwargs):
        raise AssertionError("Echte Netzabrufe sind in Tests verboten")

    monkeypatch.setattr(socket, "create_connection", verboten)
    monkeypatch.setattr(socket.socket, "connect", verboten)
    monkeypatch.setattr(urllib.request, "urlopen", verboten)


@pytest.fixture
def jetzt():
    return JETZT


@pytest.fixture
def fixture_json():
    return lambda name: lies(WURZEL / "tests" / "fixtures" / name)


@pytest.fixture
def kartentypen():
    return lies(WURZEL / "daten" / "kartentypen.json")


@pytest.fixture
def vereine():
    return lies(WURZEL / "daten" / "vereine.json")


@pytest.fixture
def spieler_fabrik():
    def baue(spieler_id="marco-reus", name="Marco Reus", **felder):
        return {
            "id": spieler_id, "name": name, "suchnamen": [],
            "vereine": [{"verein": "bvb", "von": 2012, "bis": 2024}],
            "liga": None, "gruppen": [], "quelle": "manuell", **felder,
        }

    return baue


@pytest.fixture
def spieler_daten(spieler_fabrik):
    return {"zu_haeufig": ["silva", "muller"], "spieler": [
        spieler_fabrik(suchnamen=["reus"]),
        spieler_fabrik("erling-haaland", "Erling Haaland", suchnamen=["haaland"], vereine=[
            {"verein": "bvb", "von": 2020, "bis": 2022},
            {"verein": "manchester-city", "von": 2022, "bis": None},
        ], liga="PL", gruppen=["fifa-kult"]),
    ]}


@pytest.fixture
def auktion_fabrik(jetzt):
    def baue(item_id="v1|100000000001|0", **felder):
        return {
            "item_id": item_id, "titel": "Marco Reus Auto", "bild": "https://i.ebayimg.com/reus.jpg",
            "preis_cent": 1250, "gebote": 3, "versand_cent": 180,
            "ende": "2026-11-07T12:00:00Z",
            "zuerst_gesehen": jetzt, "zuletzt_gesehen": jetzt,
            "spieler": ["marco-reus"], "vereine": ["bvb"], "typen": ["auto"],
            "verdaechtig": False, "status": "laufend", "endpreis_cent": None, **felder,
        }

    return baue


@pytest.fixture
def daten_ordner(tmp_path, spieler_daten):
    daten = tmp_path / "daten"
    for name in ("spieler.json", "vereine.json", "kartentypen.json", "suchen.json"):
        schreibe(daten / name, lies(WURZEL / "daten" / name))
    schreibe(daten / "laufend.json", {"auktionen": []})
    schreibe(daten / "archiv/index.json", {"tage": []})
    schreibe(daten / "spieler.json", spieler_daten)
    return daten


@pytest.fixture
def fake_http():
    return FakeHttp


@pytest.fixture
def fake_client():
    return FakeEbayClient


@pytest.fixture
def json_lesen():
    return lies


@pytest.fixture
def json_schreiben():
    return schreibe


@pytest.fixture
def url_parameter():
    return lambda url: parse_qs(urlsplit(url).query)
