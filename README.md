# Auktionsfinder

Findet eBay.de-Auktionen für Fußball-Sammelkarten (Autos, Relics/Patches, nummerierte Karten, Rookies), ordnet sie
Spielern und Vereinen zu und archiviert jede gefundene Auktion dauerhaft. Läuft komplett über GitHub:

- **Suchlauf** (`.github/workflows/suchlauf.yml`): täglich gegen 7 und 19 Uhr sowie per Knopf „Jetzt suchen“ in der App.
- **Kader** (`.github/workflows/kader.yml`): am 1. jedes Monats aktuelle Kader von football-data.org.
- **App**: GitHub Pages, `https://dabvud.github.io/auktionsfinder/`.

## Einrichtung

### Freund: eBay-Zugang
1. Auf <https://developer.ebay.com> ein Entwicklerkonto anlegen (Freischaltung dauert bis zu zwei Werktage).
2. Unter „Application Keys“ einen **Production**-Keyset erstellen.
3. Bei „Marketplace Account Deletion“ die Ausnahme wählen (die App speichert keine Daten von eBay-Nutzern).
4. **Client ID** (App ID) und **Client Secret** (Cert ID) auf sicherem Weg weitergeben.

### Repo-Besitzer
1. Kostenlosen Schlüssel auf <https://www.football-data.org/client/register> holen.
2. Repo → Settings → Secrets and variables → Actions: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `FOOTBALL_DATA_KEY`.
3. Repo → Settings → Pages → Source: **GitHub Actions**.
4. Actions → „kader“ einmal von Hand starten, danach „suchlauf“.
5. Zugangsschlüssel für die App: github.com → Settings → Developer settings → Fine-grained tokens → Generate new token.
   Repository access: nur `auktionsfinder`. Permissions: **Contents** und **Actions** jeweils „Read and write“.
   In der App über das Zahnrad eintragen (bleibt nur in diesem Browser).

## Hinweise

- Endpreise: eBay liefert für beendete Auktionen keine Sammelabfrage; das Archiv zeigt den **zuletzt gesehenen** Preis.
- GitHub pausiert Zeitpläne in Repos ohne Aktivität nach 60 Tagen. Die Daten-Commits der Suchläufe zählen als Aktivität;
  falls der Zeitplan trotzdem pausiert, unter Actions → suchlauf → „Enable workflow“ wieder einschalten.
- Messergebnisse zur eBay-Suche: `docs/klaerung.md`.

## Entwicklung

```
python -m venv .venv && .venv/Scripts/python -m pip install pytest
.venv/Scripts/python -m pytest -q
node --test web/filter.test.mjs web/github.test.mjs
```

Spielerlisten ergänzen: Entwurf nach `daten/entwurf/` legen, prüfen, dann
`python tools/uebernehmen.py daten/entwurf/<datei>.json --gruppe <gruppe>`.
