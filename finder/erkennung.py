"""Spieler, Vereine und Kartentypen im Angebotstitel erkennen."""

from dataclasses import dataclass
from functools import lru_cache
import re

from .normalisieren import vereinheitliche
from .spieler import SpielerIndex

MAX_WOERTER = 8  # längere Suchnamen/Stichwörter werden nicht erkannt


@dataclass
class Erkennung:
    spieler: list[str]
    vereine: list[str]
    typen: list[str]
    verdaechtig: bool
    fussball: bool


@lru_cache(maxsize=None)
def _norm(wort: str) -> str:
    return vereinheitliche(wort)


def _wortgruppen(titel: str) -> set[str]:
    """Alle zusammenhängenden Wortfolgen des vereinheitlichten Titels (bis MAX_WOERTER Wörter)."""
    woerter = vereinheitliche(titel).split()
    return {" ".join(woerter[i:i + n]) for i in range(len(woerter))
            for n in range(1, MAX_WOERTER + 1) if i + n <= len(woerter)}


def erkenne(titel: str, such_typ: str | None, index: SpielerIndex,
            vereine: dict, kartentypen: dict) -> Erkennung:
    """Nur ganze Wortfolgen treffen; Saisonangaben nicht als Nummer werten."""
    gruppen = _wortgruppen(titel)

    def trifft(wort):
        return _norm(wort) in gruppen

    spieler = {kennung for name in gruppen & index.namen.keys() for kennung in index.namen[name]}
    clubs = {v["verein"] for kennung in spieler for v in index.spieler[kennung].get("vereine", [])}
    clubs.update(kennung for kennung, v in vereine.items() if any(map(trifft, v.get("stichwoerter", []))))
    typen = set()
    for typ, konfiguration in kartentypen["typen"].items():
        if (typ == such_typ and konfiguration.get("typ_aus_suche", False)
                or any(map(trifft, konfiguration.get("titel", [])))):
            typen.add(typ)
    ohne_saison = re.sub(r"\b(?:19|20)\d{2}\s*/\s*(?:(?:19|20)\d{2}|\d{2})\b", " ", titel)
    # Kurze Saison "23/24" (zweite Zahl = erste + 1) ist keine Nummerierung; "12/99" schon.
    ohne_saison = re.sub(r"\b(\d{2})\s*/\s*(\d{2})\b",
                         lambda m: " " if (int(m[1]) + 1) % 100 == int(m[2]) else m[0], ohne_saison)
    if re.search(r"/\s*\d{1,4}\b", ohne_saison):
        typen.add("nummeriert")
    return Erkennung(
        sorted(spieler), sorted(clubs), sorted(typen),
        any(map(trifft, kartentypen.get("verdaechtig", []))),
        any(map(trifft, kartentypen.get("fussball", []))),
    )
