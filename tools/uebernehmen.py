"""Einen geprüften Entwurf in daten/spieler.json übernehmen.

Aufruf: python tools/uebernehmen.py daten/entwurf/fifa_kult.json --gruppe fifa-kult [--daten daten]
Einträge mit "sicher": false werden nur mit --mit-unsicheren übernommen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finder.jsondatei import lese_json, schreibe_json  # noqa: E402
from finder.spieler import uebernehme_entwurf  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Spieler-Entwurf übernehmen")
    parser.add_argument("entwurf", type=Path)
    parser.add_argument("--gruppe", required=True)
    parser.add_argument("--daten", type=Path, default=Path("daten"))
    parser.add_argument("--mit-unsicheren", action="store_true")
    argumente = parser.parse_args()

    entwurf = json.loads(argumente.entwurf.read_text(encoding="utf-8"))
    if not argumente.mit_unsicheren:
        entwurf = [e for e in entwurf if e.get("sicher", True)]
    pfad = argumente.daten / "spieler.json"
    vorher = lese_json(pfad, {"zu_haeufig": [], "spieler": []})
    nachher = uebernehme_entwurf(vorher, entwurf, argumente.gruppe)
    schreibe_json(pfad, nachher)
    print(f"{len(entwurf)} Einträge übernommen, jetzt {len(nachher['spieler'])} Spieler.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
