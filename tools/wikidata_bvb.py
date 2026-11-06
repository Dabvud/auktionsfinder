"""Entwurf „BVB seit 2000“ aus Wikidata erzeugen.

Aufruf: python tools/wikidata_bvb.py [ziel]   (Standard: daten/entwurf/bvb_seit_2000.json)
Holt alle Personen mit „Mitglied der Sportmannschaft“ (P54) = Borussia Dortmund (Q41420), deren Zeit dort
2000 oder später endete bzw. noch läuft. Das Ergebnis ist nur ein Entwurf und wird vor dem Übernehmen geprüft.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENDPUNKT = "https://query.wikidata.org/sparql"
ABFRAGE = """
SELECT ?person ?name ?start ?ende WHERE {
  ?person p:P54 ?st .
  ?st ps:P54 wd:Q41420 .
  OPTIONAL { ?st pq:P580 ?start . }
  OPTIONAL { ?st pq:P582 ?ende . }
  ?person wdt:P106 wd:Q937857 .
  FILTER(!BOUND(?ende) || YEAR(?ende) >= 2000)
  FILTER(!BOUND(?start) || YEAR(?start) >= 1985)
  ?person rdfs:label ?name . FILTER(LANG(?name) = "de")
}
"""


def abrufen() -> list[dict]:
    url = ENDPUNKT + "?" + urllib.parse.urlencode({"query": ABFRAGE, "format": "json"})
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Auktionsfinder/0.1 (privates Projekt)"})
    with urllib.request.urlopen(anfrage, timeout=120) as antwort:
        return json.load(antwort)["results"]["bindings"]


def jahr(zeile: dict, feld: str) -> int | None:
    wert = zeile.get(feld, {}).get("value")
    return int(wert[:4]) if wert and wert[:4].isdigit() else None


def entwurf(zeilen: list[dict]) -> list[dict]:
    spieler: dict[str, dict] = {}
    for z in zeilen:
        qid = z["person"]["value"].rsplit("/", 1)[-1]
        eintrag = spieler.setdefault(qid, {"name": z["name"]["value"], "wikidata": qid, "vereine": []})
        zeit = {"verein": "bvb", "von": jahr(z, "start"), "bis": jahr(z, "ende")}
        if zeit not in eintrag["vereine"]:
            eintrag["vereine"].append(zeit)
    # Ohne Start- und Enddatum lässt sich nicht sagen, ob jemand nach 2000 beim BVB war (meist alte Einträge) → weglassen.
    liste = [s for s in spieler.values() if any(v["von"] or v["bis"] for v in s["vereine"])]
    for s in liste:
        s["vereine"] = [v for v in s["vereine"] if v["von"] or v["bis"]]
    for s in liste:
        s["vereine"].sort(key=lambda v: v["von"] or 0)
    liste.sort(key=lambda s: (s["vereine"][0]["von"] or 0, s["name"]))
    return liste


def main() -> int:
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "daten/entwurf/bvb_seit_2000.json")
    liste = entwurf(abrufen())
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(liste, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(liste)} Spieler -> {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
