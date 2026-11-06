"""eBay-Abfragen fuer Kartentypen und gespeicherte Suchen planen."""

from dataclasses import dataclass

from .normalisieren import vereinheitliche
from .spieler import SpielerIndex


@dataclass(frozen=True)
class Suche:
    q: str
    typ: str
    aspekt: bool


def oder_gruppen(begriffe: list[str], max_len: int = 100) -> list[str]:
    """Begriffe ohne Abschneiden auf begrenzte ODER-Gruppen verteilen."""
    gruppen, aktuell = [], []
    for begriff in begriffe:
        if len(begriff) + 2 > max_len:
            raise ValueError("Suchname ist fuer eine ODER-Gruppe zu lang")
        if aktuell and len("(" + ", ".join([*aktuell, begriff]) + ")") > max_len:
            gruppen.append("(" + ", ".join(aktuell) + ")")
            aktuell = []
        aktuell.append(begriff)
    if aktuell:
        gruppen.append("(" + ", ".join(aktuell) + ")")
    return gruppen


def _passt(spieler: dict, filterwerte: dict) -> bool:
    """Auswahlfelder einer gespeicherten Suche gemeinsam anwenden."""
    return (
        (not filterwerte.get("spieler") or spieler["id"] == filterwerte["spieler"])
        and (not filterwerte.get("verein") or any(
            v["verein"] == filterwerte["verein"] for v in spieler.get("vereine", [])))
        and (not filterwerte.get("gruppe") or filterwerte["gruppe"] in spieler.get("gruppen", []))
        and (not filterwerte.get("liga") or spieler.get("liga") == filterwerte["liga"])
    )


def plane_suchen(kartentypen: dict, suchen: dict, index: SpielerIndex, vereine: dict) -> list[Suche]:
    """Jede eindeutige Abfrage mit und ohne Fussball-Aspekt planen."""
    abfragen = [(q, typ) for typ, konfiguration in kartentypen["typen"].items()
                if typ != "alle" for q in konfiguration.get("suchen", [])]
    for suche in suchen.get("suchen", []):
        filterwerte = suche["filter"]
        if filterwerte.get("typ") != "alle" or not any(
                filterwerte.get(feld) for feld in ("spieler", "verein", "gruppe")):
            continue
        namen = sorted({vereinheitliche(s["name"]).split()[-1]
                        for s in index.spieler.values() if _passt(s, filterwerte)})
        abfragen.extend((q, "alle") for q in oder_gruppen(namen))
    return list(dict.fromkeys(Suche(q, typ, aspekt) for q, typ in abfragen for aspekt in (True, False)))
