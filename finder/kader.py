"""Aktuelle Kader importieren, vorhandene Spieler und Historien erhalten."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.request

from .jsondatei import lese_json, schreibe_json
from .normalisieren import vereinheitliche

LIGEN = ("BL1", "PL", "PD", "SA", "FL1", "DED", "PPL")


def _verein(vereine: dict, team: dict, liga: str) -> str:
    """Bekannten Verein anhand der API-ID finden, sonst anlegen."""
    for kennung, verein in vereine.items():
        if verein.get("football_data_id") == team["id"]:
            verein["liga"] = liga
            return kennung
    basis = vereinheitliche(team["name"]).replace(" ", "-")
    kennung = basis if basis not in vereine else f"{basis}-{team['id']}"
    stichwoerter = list(dict.fromkeys(vereinheitliche(name) for name in (
        team.get("shortName") or team["name"], team["name"])))
    vereine[kennung] = {"name": team["name"], "liga": liga,
                        "stichwoerter": stichwoerter, "football_data_id": team["id"]}
    return kennung


def _zugehoerigkeit(spieler: dict, verein: str, jahr: int) -> None:
    """Offene Vereinszeiten fortfuehren oder einen Wechsel ergaenzen."""
    historie = spieler.setdefault("vereine", [])
    for eintrag in historie:
        if eintrag.get("bis") is None and eintrag["verein"] != verein:
            eintrag["bis"] = jahr
    if not any(e["verein"] == verein and e.get("bis") is None for e in historie):
        historie.append({"verein": verein, "von": jahr, "bis": None})


def importiere_kader(spieler_daten: dict, vereine: dict, liga: str,
                     teams: list[dict], jahr: int) -> tuple[dict, dict]:
    """Kader auf Kopien abgleichen; manuelle Namen und Quellen bewahren."""
    daten, neue_vereine = deepcopy(spieler_daten), deepcopy(vereine)
    nach_id = {s["id"]: s for s in daten["spieler"]}
    nach_name = {vereinheitliche(s["name"]): s for s in daten["spieler"]}
    gesehen = set()
    for team in teams:
        verein = _verein(neue_vereine, team, liga)
        for person in team["squad"]:
            kennung = f"fd-{person['id']}"
            spieler = nach_id.get(kennung)
            if spieler is None:
                spieler = nach_name.get(vereinheitliche(person["name"]))
            if spieler is None:
                spieler = {"id": kennung, "name": person["name"], "suchnamen": [],
                           "vereine": [], "liga": liga, "gruppen": [], "quelle": "football-data"}
                daten["spieler"].append(spieler)
                nach_id[kennung] = spieler
                nach_name[vereinheitliche(person["name"])] = spieler
            if spieler["quelle"] == "football-data":
                spieler["name"] = person["name"]
            spieler["liga"] = liga
            _zugehoerigkeit(spieler, verein, jahr)
            gesehen.add(spieler["id"])
    for spieler in daten["spieler"]:
        if (spieler["quelle"] == "football-data" and spieler.get("liga") == liga
                and spieler["id"] not in gesehen):
            spieler["liga"] = None
    return daten, neue_vereine


def hole_kader(schluessel: str, pause: float = 6.5) -> list[tuple[str, list[dict]]]:
    """Alle sieben Ligen abrufen, zwischen Abrufen das API-Limit beachten."""
    ergebnisse = []
    for nummer, liga in enumerate(LIGEN):
        if nummer and pause > 0:
            time.sleep(pause)
        anfrage = urllib.request.Request(
            f"https://api.football-data.org/v4/competitions/{liga}/teams",
            headers={"X-Auth-Token": schluessel},
        )
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:
            if antwort.status >= 400:
                raise ValueError("football-data HTTP-Fehler")
            teams = json.load(antwort)["teams"]
            if not isinstance(teams, list) or any(not isinstance(t.get("squad"), list) for t in teams):
                raise ValueError("Ungueltige Kaderdaten")
            ergebnisse.append((liga, teams))
    return ergebnisse


def main() -> int:
    """Alle Abrufe vor dem Speichern von Spielern und Vereinen abschliessen."""
    parser = argparse.ArgumentParser(description="Fussball-Kader aktualisieren")
    parser.add_argument("--daten", type=Path, default=Path("daten"))
    argumente = parser.parse_args()
    schluessel = os.environ.get("FOOTBALL_DATA_KEY", "")
    if not schluessel:
        print("football-data-Schluessel fehlt")
        return 1
    try:
        daten = lese_json(argumente.daten / "spieler.json", {"zu_haeufig": [], "spieler": []})
        vereine = lese_json(argumente.daten / "vereine.json", {})
        kader = hole_kader(schluessel)
        jahr = datetime.now(timezone.utc).year
        for liga, teams in kader:
            daten, vereine = importiere_kader(daten, vereine, liga, teams, jahr)
        schreibe_json(argumente.daten / "spieler.json", daten)
        schreibe_json(argumente.daten / "vereine.json", vereine)
    except Exception:
        print("Kader-Import fehlgeschlagen; Abrufe oder Daten pruefen.")
        return 1
    print(f"Kader aktualisiert: {len(daten['spieler'])} Spieler.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
