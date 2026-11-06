"""Spielernamen indizieren und gepruefte Entwuerfe ergaenzen."""

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass

from .normalisieren import vereinheitliche


@dataclass(frozen=True)
class SpielerIndex:
    namen: dict[str, tuple[str, ...]]
    spieler: dict[str, dict]


def baue_index(daten: dict) -> SpielerIndex:
    """Vollnamen und gepflegte Suchnamen sammeln."""
    spieler = {eintrag["id"]: eintrag for eintrag in daten["spieler"]}
    namen = defaultdict(set)
    for kennung, eintrag in spieler.items():
        # Nur voller Name und gepflegte Suchnamen: ein Nachname allein traf im echten Lauf meist den Falschen.
        eigene = {vereinheitliche(name) for name in eintrag.get("suchnamen", [])}
        eigene.add(vereinheitliche(eintrag["name"]))
        for name in eigene - {""}:
            namen[name].add(kennung)
    return SpielerIndex({name: tuple(sorted(ids)) for name, ids in namen.items()}, spieler)


def uebernehme_entwurf(daten: dict, entwurf: list[dict], gruppe: str, quelle: str = "manuell") -> dict:
    """Gepruefte Spieler ohne Verlust bestehender Daten uebernehmen."""
    neu = deepcopy(daten)
    nach_name = {vereinheitliche(s["name"]): s for s in neu["spieler"]}
    for eintrag in entwurf:
        name = vereinheitliche(eintrag["name"])
        if name not in nach_name:
            kennung = name.replace(" ", "-")
            belegt = {s["id"] for s in neu["spieler"]}
            basis, nummer = kennung, 2
            while kennung in belegt:
                kennung = f"{basis}-{nummer}"
                nummer += 1
            spieler = {
                "id": kennung, "name": eintrag["name"], "suchnamen": [],
                "vereine": [], "liga": None, "gruppen": [], "quelle": quelle,
            }
            neu["spieler"].append(spieler)
            nach_name[name] = spieler
        spieler = nach_name[name]
        spieler["gruppen"] = sorted(set(spieler.get("gruppen", [])) | {gruppe})
        for feld in ("vereine", "suchnamen"):
            ziel = spieler.setdefault(feld, [])
            for wert in eintrag.get(feld, []):
                if wert not in ziel:
                    ziel.append(deepcopy(wert))
    return neu


def pflege_favoriten(daten: dict, namen: list[str]) -> dict:
    """Gruppe "favorit" genau an die Favoriten vergeben, Unbekannte als Spieler anlegen."""
    neu = deepcopy(daten)
    for spieler in neu["spieler"]:
        if "favorit" in spieler.get("gruppen", []):
            spieler["gruppen"].remove("favorit")
    index = baue_index(neu)
    entwurf = []
    for name in namen:
        name = " ".join(name.split())
        treffer = index.namen.get(vereinheitliche(name), ())
        if name:
            # Eindeutiger Suchname ("Haaland") meint den vorhandenen Spieler, nicht einen neuen.
            entwurf.append({"name": index.spieler[treffer[0]]["name"] if len(treffer) == 1 else name})
    return uebernehme_entwurf(neu, entwurf, "favorit", quelle="favorit")
