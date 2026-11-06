"""Auktionen aktualisieren und ausschliesslich nach Endzeit archivieren."""

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .jsondatei import lese_json, schreibe_auktionen, schreibe_json


def _zeit(wert: str) -> datetime:
    return datetime.fromisoformat(wert.replace("Z", "+00:00")).astimezone(timezone.utc)


def _vereinige(alt: dict, neu: dict) -> dict:
    """Aktuelle Daten mit bisherigen Zuordnungen zusammenfuehren."""
    ergebnis = {**deepcopy(alt), **deepcopy(neu), "zuerst_gesehen": alt["zuerst_gesehen"]}
    for feld in ("spieler", "vereine", "typen"):
        ergebnis[feld] = sorted(set(alt.get(feld, [])) | set(neu.get(feld, [])))
    ergebnis["verdaechtig"] = alt.get("verdaechtig", False) or neu.get("verdaechtig", False)
    return ergebnis


def einpflegen(laufend: list[dict], gefunden: list[dict], jetzt: str) -> tuple[list[dict], list[dict], int]:
    """Treffer vereinigen; fehlende Auktionen bis zu ihrem Ende erhalten."""
    bestand = {a["item_id"]: deepcopy(a) for a in laufend}
    anzahl_neu = 0
    for treffer in gefunden:
        kennung = treffer["item_id"]
        treffer = {**treffer, "zuletzt_gesehen": jetzt}
        if kennung in bestand:
            bestand[kennung] = _vereinige(bestand[kennung], treffer)
        else:
            bestand[kennung] = deepcopy(treffer)
            anzahl_neu += 1
    aktiv, beendet = [], []
    zeitpunkt = _zeit(jetzt)
    for auktion in bestand.values():
        if auktion.get("ende") and _zeit(auktion["ende"]) < zeitpunkt:
            auktion.update(status="beendet", endpreis_cent=auktion["preis_cent"])
            beendet.append(auktion)
        else:
            aktiv.append(auktion)
    schluessel = lambda a: _zeit(a["ende"]) if a.get("ende") else datetime.max.replace(tzinfo=timezone.utc)
    return sorted(aktiv, key=schluessel), sorted(beendet, key=schluessel), anzahl_neu


def archiviere(beendet: list[dict], archiv_dir: Path) -> None:
    """UTC-Tagesdateien um eindeutige Auktionen ergaenzen, alte Tage erhalten."""
    archiv_dir = Path(archiv_dir)
    tage = set(lese_json(archiv_dir / "index.json", {"tage": []}).get("tage", []))
    gruppen = defaultdict(list)
    for auktion in beendet:
        gruppen[_zeit(auktion["ende"]).strftime("%Y-%m-%d")].append(auktion)
    for tag, auktionen in gruppen.items():
        pfad = archiv_dir / f"{tag}.json"
        bestand = {a["item_id"]: a for a in lese_json(pfad, {"auktionen": []})["auktionen"]}
        for auktion in auktionen:
            kennung = auktion["item_id"]
            bestand[kennung] = _vereinige(bestand[kennung], auktion) if kennung in bestand else auktion
        schreibe_auktionen(pfad, sorted(bestand.values(), key=lambda a: _zeit(a["ende"])))
        tage.add(tag)
    if gruppen:
        schreibe_json(archiv_dir / "index.json", {"tage": sorted(tage, reverse=True)})
