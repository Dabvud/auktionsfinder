# Auktionsfinder

Findet eBay.de-Auktionen für Fußball-Sammelkarten (Autos, Relics/Patches, nummerierte Karten, Rookies), ordnet sie
Spielern und Vereinen zu und archiviert jede gefundene Auktion dauerhaft. Läuft komplett über GitHub:

- **Suchlauf** (`.github/workflows/suchlauf.yml`): täglich gegen 7 und 19 Uhr sowie per Knopf „Jetzt suchen“ in der App.
- **Kader** (`.github/workflows/kader.yml`): am 1. jedes Monats aktuelle Kader von football-data.org.
- **App**: GitHub Pages unter `https://<dein-github-name>.github.io/<repo-name>/`.

Dieses Repo ist eine **Vorlage**. Jede Person richtet sich ihre eigene Kopie mit eigenen Schlüsseln ein. Suchläufe,
eBay-Kontingent (5.000 Abfragen am Tag) und Daten gehören dann ganz ihr. Ohne eingetragene Schlüssel tut eine Kopie
nichts: Suchlauf und Kader werden mit einem Hinweis übersprungen.

## Eigene Kopie einrichten (ca. 20 Minuten, plus Wartezeit bei eBay)

### 1. GitHub
1. Kostenloses Konto auf <https://github.com> anlegen (falls noch keins da ist).
2. Auf der Seite dieser Vorlage oben rechts **„Use this template“ → „Create a new repository“**.
   Name z. B. `auktionsfinder`, Sichtbarkeit **Public** (sonst gibt es GitHub Pages nicht kostenlos).

### 2. eBay-Schlüssel (eigener, Pflicht)
1. Auf <https://developer.ebay.com> ein Entwicklerkonto anlegen (Freischaltung dauert bis zu zwei Werktage).
2. Unter „Application Keys“ einen **Production**-Keyset erstellen (nicht Sandbox: Sandbox-Schlüssel enthalten „SBX“).
3. Bei „Marketplace Account Deletion“ die Ausnahme wählen (die App speichert keine Daten von eBay-Nutzern).
4. Notieren: **App ID (Client ID)**, sieht aus wie `Name-App-PRD-…`, und **Cert ID (Client Secret)**, beginnt mit `PRD-`.

### 3. Kader-Schlüssel
Kostenlos auf <https://www.football-data.org/client/register>, kommt per E-Mail.

### 4. Schlüssel eintragen
In deinem neuen Repo: **Settings → Secrets and variables → Actions → „New repository secret“**, dreimal:

| Name | Wert |
|---|---|
| `EBAY_CLIENT_ID` | App ID (Client ID) |
| `EBAY_CLIENT_SECRET` | Cert ID (Client Secret) |
| `FOOTBALL_DATA_KEY` | Schlüssel von football-data.org |

Ohne Leerzeichen oder Zeilenumbruch am Anfang oder Ende einfügen.

### 5. Seite einschalten und starten
1. **Settings → Pages → Source: „GitHub Actions“**.
2. **Actions**: falls gefragt, Workflows erlauben. Dann „kader“ → „Run workflow“, danach „suchlauf“ → „Run workflow“.
3. Nach ein paar Minuten ist die App unter `https://<dein-github-name>.github.io/<repo-name>/` erreichbar.
   Ab dann sucht sie täglich gegen 7 und 19 Uhr von selbst.

### 6. Zugangsschlüssel für die App (zum Speichern von Suchen, Favoriten und für „Jetzt suchen“)
github.com → Settings → Developer settings → **Fine-grained tokens → Generate new token**.
Repository access: nur dein Auktionsfinder-Repo. Permissions: **Contents** und **Actions** jeweils „Read and write“.
In der App über das Zahnrad eintragen (bleibt nur in diesem Browser).

Verbesserungen an der Vorlage kommen nicht automatisch in deine Kopie.

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
