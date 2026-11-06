# Auktionsfinder – Design

Stand: 2026-11-06 · Arbeitsname „Auktionsfinder“, Repo-Name vorläufig `Dabvud/auktionsfinder`

## Ziel

Ein Freund sammelt Fußball-Sportkarten. Die App findet für ihn **eBay-Auktionen** zu Spielern, Vereinen und Kartentypen,
zeigt sie gebündelt an und **archiviert jede gefundene Auktion dauerhaft**, damit nichts verloren geht.

Erfolg: Jede passende Auktion auf eBay.de taucht mindestens einmal vor ihrem Ende in der App auf und bleibt danach im Archiv.

## Nicht-Ziele

- Keine Marktpreise, Margen oder Kaufempfehlungen (anders als Bisasaldo).
- Keine Benachrichtigungen (vorerst; der Freund merkt Auktionen per Herz bei eBay).
- Kein Bieten über die App.
- Kein Betrieb auf dem Raspberry Pi des Nutzers – alles läuft über GitHub.

## Architektur

Ein öffentliches GitHub-Repo mit drei Teilen:

1. **Spieler-Datenbank** – JSON-Dateien im Repo.
2. **Suchlauf** – Python-Skript in GitHub Actions, sucht bei eBay, schreibt Treffer ins Repo, veröffentlicht die Seite neu.
3. **App** – statische Seite auf GitHub Pages (HTML/CSS/JS ohne Build-Schritt), liest die JSON-Dateien.

Geheimnisse liegen als **Repo-Secrets** (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `FOOTBALL_DATA_KEY`) und nie im Code oder auf der Seite.

### Ablauf

```
Zeitplan 07:00 + 19:00 dt. Zeit ┐
Knopf „Jetzt suchen“ (App)  ───┴─► Workflow „suchlauf“ (concurrency: eine Instanz, weitere warten)
                                     1. eBay-Token (client_credentials, Browse API)
                                     2. je Kartentyp eine Suche, alle Seiten (limit 200)
                                     3. je gespeicherter „Alle Karten“-Suche eine Namenssuche
                                     4. Titel ↔ Spieler-Datenbank abgleichen
                                     5. ins Archiv einpflegen (neu / aktualisieren / beendet)
                                     6. Endpreise beendeter Auktionen nachholen (getItems, 20 je Abfrage)
                                     7. status.json schreiben, committen (vorher pull --rebase), Pages deployen
```

Cron läuft in UTC; die Zeiten werden so gewählt, dass sie auch bei Sommerzeit ungefähr stimmen (Abweichung ±1 h ist unkritisch).

Monatlich zusätzlich Workflow „kader“: aktuelle Kader von football-data.org holen und `spieler.json` aktualisieren.

## Daten

### `daten/spieler.json`

```json
{
  "id": "victor-ibarbo",
  "name": "Víctor Ibarbo",
  "suchnamen": ["victor ibarbo", "ibarbo"],
  "vereine": [{"verein": "cagliari", "von": 2011, "bis": 2015}],
  "liga": null,
  "gruppen": ["fifa-kult"],
  "quelle": "manuell"
}
```

- `suchnamen` sind bereits vereinheitlicht (siehe Erkennung). Standard: „vorname nachname“. Den Nachnamen allein nur, wenn er
  in der gesamten Datenbank eindeutig und nicht als zu häufig markiert ist.
- `liga` = aktuelle Liga (nur für Spieler aus aktuellen Kadern), sonst `null`.
- `gruppen`: `bvb-seit-2000`, `bvb-legende`, `fifa-kult` (erweiterbar).
- `quelle`: `football-data`, `wikidata`, `manuell`. Der Kader-Workflow überschreibt nur Einträge mit Quelle `football-data`
  und ergänzt Vereine bei bestehenden Spielern, statt sie zu löschen.

### `daten/vereine.json`

Verein → Anzeigename, Liga, Titel-Stichwörter (z. B. `bvb` → „BVB“, „Borussia Dortmund“, „Dortmund“).

### `daten/kartentypen.json`

| Typ | eBay-Suchbegriffe | Titel-Stichwörter |
|---|---|---|
| auto | auto, autograph, signed, signature, signiert, autogramm | dieselben |
| relic | relic, patch, jersey, memorabilia, „game worn“, trikot | dieselben |
| nummeriert | numbered, nummeriert (+ „/99“ usw., falls eBay das sinnvoll sucht – beim Bau testen) | Muster `/\d{1,4}\b` |
| rookie | rookie, rc | dieselben |

`verdaechtig`: facsimile, reprint, custom, „printed signature“, „pre-print“, „preprint“, replica.

### `daten/suchen.json` – gespeicherte Suchen

```json
{"id": "bvb-autos", "name": "BVB Autos", "filter": {"typ": "auto", "verein": "bvb", "liga": null,
 "spieler": null, "gruppe": null, "max_preis": null}}
```

Typ `alle` ist nur zusammen mit Spieler, Verein oder Gruppe erlaubt und löst im Suchlauf eine Namenssuche aus
(Spielernamen als ODER-Gruppen, Suchstring höchstens 100 Zeichen, also mehrere Abfragen je Suche).

### `daten/laufend.json` und `daten/archiv/JJJJ-MM.json`

Je Auktion: `item_id`, `titel`, `bild`, `url`, `preis_cent`, `waehrung`, `gebote`, `versand_cent`, `start`, `ende`,
`zuerst_gesehen`, `zuletzt_gesehen`, `spieler` (IDs), `vereine`, `typen`, `verdaechtig`, `status` (`laufend`/`beendet`),
`endpreis_cent`.

- Neue Auktion → `laufend.json`.
- Bekannte → Preis, Gebote, `zuletzt_gesehen` aktualisieren.
- **Beendet nur, wenn `ende` < jetzt** – nie, weil sie in einem Lauf fehlt. Dann wandert sie ins Monatsarchiv ihres Endes.
- Es wird **nie** etwas gelöscht.

### `daten/status.json`

Letzter Lauf: Start, Ende, Erfolg/Fehlermeldung, Zahl gefundener/neuer Auktionen, verbrauchte eBay-Abfragen.

## Suchlauf

- eBay Browse API `item_summary/search`, Marketplace `EBAY_DE`, Filter `buyingOptions:{AUCTION}`, Kategorie
  Fußball-Sammelkarten (ID beim Bau ermitteln und als Konstante festhalten), alle Seiten bis zum Ende der Ergebnisse.
- ODER-Suche über die Browse-Syntax `(begriff1, begriff2)`.
- Geschätzter Verbrauch: 10–40 Abfragen je Lauf, also weit unter dem Tageskontingent von 5.000.
- Liefert eine Suche mehr als 10.000 Treffer (Offset-Grenze der API), wird sie nach Preisspannen aufgeteilt.

## Treffererkennung

1. **Vereinheitlichen:** Kleinbuchstaben, Akzente entfernen (Unicode NFKD), ß → ss, Satzzeichen → Leerzeichen,
   Mehrfach-Leerzeichen zusammenfassen.
2. **Spieler:** Ein Suchname trifft nur als ganze Wortfolge (Wortgrenzen). Mehrere Spieler pro Titel sind möglich.
3. **Verein:** Vereine aller erkannten Spieler **plus** Vereine, deren Titel-Stichwörter im Titel stehen.
4. **Typen:** Typ der auslösenden Suche plus alle Typen, deren Titel-Stichwörter im Titel stehen.
5. **Verdächtig:** Titel enthält ein Wort aus der Verdächtig-Liste → markiert, in der App standardmäßig ausgeblendet.
6. Ohne erkannten Spieler → bleibt erhalten und erscheint im Filter **„Nicht zugeordnet“**.

## App

- Fürs Handy gebaut, funktioniert am PC.
- **Kopfzeile:** letzter Lauf (Zeit, Anzahl, ggf. Fehlermeldung) und Knopf **„Jetzt suchen“** (startet `workflow_dispatch`,
  fragt den Laufstatus ab, lädt danach neu).
- **Gespeicherte Suchen** als Knöpfe oben; Tippen setzt die Filter. „Speichern“ legt die aktuelle Filterkombination mit Namen an;
  Löschen über ein Menü am Knopf.
- **Filter:** Kartentyp, Liga, Verein, Gruppe, Spieler (mit Suchfeld), Höchstpreis, Ende in 24 h / 3 Tagen / 7 Tagen
  (Standard 7 Tage), „Verdächtige anzeigen“, „Nicht zugeordnet“.
- **Reiter:** „Laufend“ (nach Ende sortiert) und „Archiv“ (beendet, mit Endpreis, Monat wählbar).
- **Kärtchen:** Bild, Titel, Preis, Gebote, Restzeit, Versand, erkannte Spieler und Vereine, Knopf „Bei eBay öffnen“.
- Daten werden über die GitHub-API geladen (nicht über den Pages-Cache), damit die App direkt nach einem Lauf aktuell ist;
  ohne Schlüssel greift sie auf die mitveröffentlichten Dateien zurück.

### Schreibzugriff

- Ein **fein abgestufter GitHub-Zugangsschlüssel** nur für dieses Repo mit den Rechten *Contents: Read and write* und
  *Actions: Read and write*.
- Liegt ausschließlich im `localStorage` seines Browsers; Eingabe über einen Einstellungsdialog mit Anleitung.
- Ohne Schlüssel: Ansehen und Filtern gehen, Speichern und „Jetzt suchen“ sind ausgegraut.

## Spieler-Datenbank: Aufbau

| Bestand | Quelle | Prüfung |
|---|---|---|
| Aktuelle Kader: Bundesliga, Premier League, LaLiga, Serie A, Ligue 1, Eredivisie, Primeira Liga | football-data.org (kostenlose Stufe), monatlich | stichprobenartig |
| BVB-Spieler seit 2000 | Wikidata (Vereinszugehörigkeit mit Zeitangaben) | Liste dem Nutzer vorlegen |
| BVB-Legenden (auch vor 2000) | Codex stellt zusammen | Liste dem Nutzer vorlegen |
| FIFA-Kultspieler (z. B. Ibarbo) | Codex stellt zusammen | Liste dem Nutzer vorlegen |

Grenzfälle (gehört jemand dazu oder nicht?) entscheidet der Nutzer, nicht Codex oder Claude.

## Fehlerbehandlung

- eBay-Fehler, Zeitüberschreitung oder Kontingent erschöpft → Lauf bricht ab, bestehende Daten bleiben unverändert,
  `status.json` enthält die Fehlermeldung, die App zeigt „Letzter Lauf fehlgeschlagen: …“.
- Ein abgebrochener Lauf kann nichts als beendet markieren oder löschen (siehe Archivregeln).
- Commit-Konflikt → `pull --rebase` und ein erneuter Versuch; Lauf und App schreiben in verschiedene Dateien.
- football-data.org nicht erreichbar → Kader bleiben wie sie sind.
- GitHub pausiert Zeitpläne nach 60 Tagen ohne Repo-Aktivität: prüfen, ob die Daten-Commits genügen; sonst
  Gegenmaßnahme einbauen (z. B. Keepalive-Schritt).

## Tests

- pytest für: Vereinheitlichen, Namenserkennung (Akzente, Wortgrenzen, „Silva“-Fall, mehrere Spieler), Vereins- und
  Typerkennung, Verdächtig-Markierung, Archivregeln (neu, aktualisiert, beendet nur nach Endzeit, nie löschen),
  Aufbau der ODER-Suchstrings (100-Zeichen-Grenze), Kader-Abgleich (überschreibt nur `football-data`-Einträge).
- eBay- und football-data-Antworten als gespeicherte Beispieldateien; keine echten Abrufe in Tests.
- Abnahme: ein echter Lauf mit den Schlüsseln des Freundes, danach Browserprüfung der Seite im Handyformat.

## Einrichtung

**Der Freund:**
1. eBay-Entwicklerkonto anlegen, Production-Keyset erstellen, bei „Marketplace Account Deletion“ die Ausnahme wählen.
2. Client ID und Client Secret dem Nutzer auf sicherem Weg geben.
3. GitHub-Konto (falls gewünscht) und fein abgestuften Zugangsschlüssel anlegen – oder der Nutzer legt ihn an und richtet ihn
   im Browser des Freundes ein.

**Der Nutzer:**
1. Kostenlosen API-Schlüssel bei football-data.org holen.
2. Repo anlegen, Secrets eintragen, Pages auf GitHub Actions umstellen.

## Beim Bau zu klären

- Kategorie-ID für Fußball-Sammelkarten auf eBay.de.
- Wie die Browse-Suche mit „/99“ umgeht.
- Ob die kostenlose Stufe von football-data.org die Kader aller sieben Ligen liefert.
- Ob Daten-Commits durch Actions die 60-Tage-Pause verhindern.
- Ob der Zugangsschlüssel des Freundes sein eigener ist (dann braucht er Schreibrechte im Repo des Nutzers) oder der des Nutzers.
