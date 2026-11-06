"""Einen vollstaendigen Suchlauf ausfuehren und seinen Status schreiben."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path

from .archiv import archiviere, einpflegen
from .ebay import EbayClient, zu_auktion
from .erkennung import erkenne
from .jsondatei import lese_json, schreibe_auktionen, schreibe_json
from .spieler import baue_index, pflege_favoriten
from .suchplan import plane_suchen


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _status(jetzt: str) -> dict:
    return {"start": jetzt, "ende": jetzt, "ok": False, "fehler": None,
            "gefunden": 0, "neu": 0, "beendet": 0, "abfragen": 0, "warnungen": []}


def _fehlertext(fehler: Exception) -> str:
    """Bekannte Umgebungsschluessel auch aus fremden Fehlertexten entfernen."""
    text = str(fehler) or "Suchlauf fehlgeschlagen"
    geheimnisse = [os.environ.get(name, "") for name in (
        "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "FOOTBALL_DATA_KEY")]
    for geheim in sorted(geheimnisse, key=len, reverse=True):
        if geheim:
            text = text.replace(geheim, "[entfernt]")
    return text


def suchlauf(daten: Path, client: EbayClient, jetzt: str) -> dict:
    """Alle Suchen vor dem ersten Schreiben von Auktionsdaten abschliessen."""
    daten = Path(daten)
    status = _status(jetzt)
    try:
        spieler_alt = lese_json(daten / "spieler.json", {"spieler": []})
        spieler_daten = pflege_favoriten(spieler_alt, lese_json(daten / "favoriten.json", {"namen": []})["namen"])
        index = baue_index(spieler_daten)
        vereine = lese_json(daten / "vereine.json", {})
        kartentypen = lese_json(daten / "kartentypen.json", {"typen": {}})
        suchen = lese_json(daten / "suchen.json", {"suchen": []})
        # Favoriten: alle Karten dieser Spieler suchen, wie eine gespeicherte Suche "alle Karten".
        suchen = {"suchen": [*suchen.get("suchen", []), {"filter": {"typ": "alle", "gruppe": "favorit"}}]}
        laufend = lese_json(daten / "laufend.json", {"auktionen": []})["auktionen"]
        gefunden = []
        for suche in plane_suchen(kartentypen, suchen, index, vereine):
            for summary in client.suche(suche.q, suche.aspekt):
                erk = erkenne(summary["title"], suche.typ, index, vereine, kartentypen)
                if suche.aspekt or erk.spieler or erk.vereine or erk.fussball:
                    gefunden.append(zu_auktion(summary, erk, jetzt))
        aktiv, beendet, neu = einpflegen(laufend, gefunden, jetzt)
        archiviere(beendet, daten / "archiv")
        schreibe_auktionen(daten / "laufend.json", aktiv)
        if spieler_daten != spieler_alt:
            schreibe_json(daten / "spieler.json", spieler_daten)
        status.update(ok=True, gefunden=len({a["item_id"] for a in gefunden}), neu=neu, beendet=len(beendet))
    except Exception as fehler:
        status["fehler"] = _fehlertext(fehler)
    finally:
        status.update(ende=_jetzt(), abfragen=client.abfragen,
                      warnungen=[_fehlertext(Exception(w)) for w in client.warnungen])
        schreibe_json(daten / "status.json", status)
    return status


def main() -> int:
    """CLI fuer einen Suchlauf mit Schluesseln aus der Umgebung."""
    parser = argparse.ArgumentParser(description="eBay-Auktionen suchen")
    parser.add_argument("--daten", type=Path, default=Path("daten"))
    argumente = parser.parse_args()
    client_id = os.environ.get("EBAY_CLIENT_ID", "")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        status = _status(_jetzt())
        status["fehler"] = "eBay-Schlüssel fehlt"
        schreibe_json(argumente.daten / "status.json", status)
    else:
        status = suchlauf(argumente.daten, EbayClient(client_id, client_secret), _jetzt())
    if status["ok"]:
        print(f"Suchlauf erfolgreich: {status['gefunden']} gefunden, {status['neu']} neu, {status['beendet']} beendet.")
    else:
        meldung = str(status["fehler"]).encode("ascii", "backslashreplace").decode("ascii")
        print(f"Suchlauf fehlgeschlagen: {meldung}")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
