from copy import deepcopy
import io
import json
import sys
import time
import urllib.error
import urllib.request

import pytest

import finder.kader as kader_modul
from finder.kader import importiere_kader


def test_neuer_spieler(fixture_json, vereine):
    teams = fixture_json("fd_bl1_teams.json")["teams"][:1]
    spieler, neue_vereine = importiere_kader({"zu_haeufig": ["silva"], "spieler": []}, vereine, "BL1", teams, 2026)
    assert sorted(s["id"] for s in spieler["spieler"]) == ["fd-1", "fd-2"]
    for eintrag, erwartet in zip(sorted(spieler["spieler"], key=lambda s: s["id"]), [
        {"id": "fd-1", "name": "Julian Brandt",
         "vereine": [{"verein": "bvb", "von": 2026, "bis": None}],
         "liga": "BL1", "gruppen": [], "quelle": "football-data"},
        {"id": "fd-2", "name": "Gregor Kobel",
         "vereine": [{"verein": "bvb", "von": 2026, "bis": None}],
         "liga": "BL1", "gruppen": [], "quelle": "football-data"},
    ], strict=True):
        assert {feld: eintrag[feld] for feld in erwartet} == erwartet
    assert spieler["zu_haeufig"] == ["silva"]
    assert neue_vereine == vereine


def test_neuer_verein(fixture_json, vereine):
    teams = fixture_json("fd_bl1_teams.json")["teams"][1:]
    spieler, neu = importiere_kader({"zu_haeufig": [], "spieler": []}, vereine, "BL1", teams, 2026)
    assert neu["fc-bayern-munchen"] == {
        "name": "FC Bayern München", "liga": "BL1", "stichwoerter": ["bayern", "fc bayern munchen"],
        "football_data_id": 5,
    }
    assert neu["bvb"] == vereine["bvb"]
    assert spieler["spieler"][0]["vereine"] == [{"verein": "fc-bayern-munchen", "von": 2026, "bis": None}]


def test_verein_stichwoerter_bleiben(fixture_json, vereine):
    vereine["bvb"]["stichwoerter"] = ["bvb", "borussia dortmund", "dortmund", "schwarzgelb"]
    vorher = deepcopy(vereine["bvb"])
    _, neu = importiere_kader({"zu_haeufig": [], "spieler": []}, vereine, "BL1", fixture_json("fd_bl1_teams.json")["teams"][:1], 2026)
    assert neu["bvb"] == vorher
    assert sorted(neu) == ["bvb"]


def test_wechsel(spieler_fabrik, fixture_json, vereine):
    alt = spieler_fabrik("fd-1", "Julian Brandt", quelle="football-data", liga="BL1", vereine=[
        {"verein": "leverkusen", "von": 2024, "bis": None},
    ])
    daten, _ = importiere_kader({"zu_haeufig": [], "spieler": [alt]}, vereine, "BL1", fixture_json("fd_bl1_teams.json")["teams"][:1], 2026)
    brandt = [s for s in daten["spieler"] if s["id"] == "fd-1"]
    assert len(brandt) == 1
    assert brandt[0]["vereine"] == [
        {"verein": "leverkusen", "von": 2024, "bis": 2026},
        {"verein": "bvb", "von": 2026, "bis": None},
    ]
    assert brandt[0]["liga"] == "BL1"
    assert brandt[0]["quelle"] == "football-data"


def test_liga_verlassen(spieler_fabrik, vereine):
    weg = spieler_fabrik("fd-1", "Julian Brandt", quelle="football-data", liga="BL1", vereine=[
        {"verein": "bvb", "von": 2024, "bis": None},
    ])
    andere_liga = spieler_fabrik("fd-9", "Erling Haaland", quelle="football-data", liga="PL", vereine=[
        {"verein": "manchester-city", "von": 2022, "bis": None},
    ])
    manuell = spieler_fabrik(liga="BL1")
    andere_liga_vorher = deepcopy(andere_liga)
    manuell_vorher = deepcopy(manuell)
    daten, _ = importiere_kader({"zu_haeufig": [], "spieler": [weg, andere_liga, manuell]}, vereine, "BL1", [], 2026)
    nach_id = {s["id"]: s for s in daten["spieler"]}
    assert sorted(nach_id) == ["fd-1", "fd-9", "marco-reus"]
    assert nach_id["fd-1"]["liga"] == None
    assert nach_id["fd-1"]["name"] == "Julian Brandt"
    assert nach_id["fd-1"]["quelle"] == "football-data"
    assert nach_id["fd-9"] == andere_liga_vorher
    assert nach_id["marco-reus"] == manuell_vorher


@pytest.mark.parametrize("quelle", ["wikidata", "manuell"])
def test_manueller_spieler_ergaenzt(spieler_fabrik, fixture_json, vereine, quelle):
    leverkusen = {"verein": "leverkusen", "von": 2014, "bis": 2019}
    alt = spieler_fabrik("julian-brandt", "Julián Brandt", quelle=quelle, suchnamen=["jule brandt"],
                        gruppen=["bvb-seit-2000"], vereine=[leverkusen])
    vorher = deepcopy(alt)
    daten, _ = importiere_kader({"zu_haeufig": [], "spieler": [alt]}, vereine, "BL1", fixture_json("fd_bl1_teams.json")["teams"][:1], 2026)
    assert sorted(s["id"] for s in daten["spieler"]) == ["fd-2", "julian-brandt"]
    brandt = next(s for s in daten["spieler"] if s["id"] == "julian-brandt")
    assert brandt == {**vorher, "liga": "BL1", "vereine": [leverkusen, {"verein": "bvb", "von": 2026, "bis": None}]}


def test_fehler_unveraendert(daten_ordner, fixture_json, monkeypatch):
    vorher = {p.relative_to(daten_ordner): p.read_bytes() for p in daten_ordner.rglob("*.json")}
    aufrufe = []

    def urlopen(request, *args, **kwargs):
        aufrufe.append(request.full_url)
        header = {name.lower(): wert for name, wert in request.header_items()}
        assert header["x-auth-token"] == "test-fd-key"
        if len(aufrufe) == 2:
            raise urllib.error.HTTPError(request.full_url, 500, "Serverfehler", {}, None)
        antwort = io.BytesIO(json.dumps(fixture_json("fd_bl1_teams.json")).encode("utf-8"))
        antwort.status = 200
        return antwort

    monkeypatch.setenv("FOOTBALL_DATA_KEY", "test-fd-key")
    monkeypatch.chdir(daten_ordner.parent)
    monkeypatch.setattr(sys, "argv", ["finder.kader"])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(kader_modul, "urlopen", urlopen, raising=False)
    monkeypatch.setattr(time, "sleep", lambda sekunden: None)
    # Auch ein direkt importiertes sleep wird ersetzt; kein Warten im Test.
    monkeypatch.setattr(kader_modul, "sleep", lambda sekunden: None, raising=False)
    assert kader_modul.main() == 1
    assert len(aufrufe) == 2
    assert aufrufe[0] == "https://api.football-data.org/v4/competitions/BL1/teams"
    assert {p.relative_to(daten_ordner): p.read_bytes() for p in daten_ordner.rglob("*.json")} == vorher
