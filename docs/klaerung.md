# Klärung eBay / football-data (Task 0, 2026-11-06)

Gemessen mit einem Production-Keyset (Browse API, client_credentials), Marketplace `EBAY_DE`.

## Kategorie

- Es gibt keine eigene Fußball-Kategorie. Fußballkarten liegen in **261328 „Trading Card Einzelkarten“**
  (Sammeln & Seltenes > Trading Cards > Sport Trading Cards), zusammen mit NBA, NFL, Formel 1 usw.
- Fußball lässt sich per Aspekt eingrenzen: `aspect_filter=categoryId:261328,Sportart:{Fußball}`.
- **Etwa 9 % der Fußball-Auktionen haben keinen Sportart-Aspekt** (Stichprobe „Auto + Dortmund/Bayern/…“: 1.388 ohne
  vs. 1.262 mit Aspektfilter; darunter echte BVB-Autos wie „Matthias Sammer Borussia Dortmund Auto“).
  → Je Suche zwei Durchgänge:
  - **A** mit Aspektfilter Fußball: jede Auktion behalten.
  - **B** ohne Aspektfilter: nur behalten, wenn ein Spieler, ein Verein oder ein Fußball-Stichwort
    (z. B. bundesliga, uefa, premier league) im Titel erkannt wird.
- Gesamtbestand Fußball-Auktionen (mit Aspekt): rund 68.000. Alles abzuholen wäre zu teuer; die Typsuchen bleiben.

## Suchsyntax

| Anfrage (mit Fußball-Aspekt) | Treffer |
|---|---|
| `auto` | 4.603 |
| `autograph` | 2.859 |
| `(auto, autograph)` | 5.435 |
| `(auto, autograph, signed, signature, signiert, autogramm)` | 6.637 |
| dieselbe ohne Aspektfilter | 13.394 |
| `(auto autograph)` (ohne Komma = UND) | 30 |
| `relic` | 864 |
| `(relic, patch, jersey, memorabilia, worn, trikot)` | 1.747 |
| `(game worn, relic)` | 737 – Mehrwort-Begriffe in ODER-Gruppen funktionieren |
| `/99` und `99` | 3.359 / 3.360 – der Schrägstrich wird ignoriert |
| `numbered` | 7.643 |
| `(numbered, nummeriert)` | 2.009 (seltsamerweise weniger als `numbered` allein) |
| `(numbered, nummeriert, 99, 75, 50, 49, 25, 10, 5)` | 19.983 – zu viel Rauschen |
| `(rookie, rc)` | 6.842 |
| `(marco reus, erling haaland)` / `(reus, haaland)` | 513 / 608 |

Folgerungen:
- Je Kartentyp eine **Liste von Suchanfragen** statt einer Begriffsliste; „Nummeriert“ sucht `numbered` und `nummeriert`
  getrennt und erkennt den Typ **nur aus dem Titel** (Muster `/\d{1,4}`, ohne Saisonangaben).
- Ergebnisse enthalten auch Auktionen aus dem Ausland (GBP umgerechnet) → Filter `deliveryCountry:DE` ergänzt.
- Mehr als 10.000 Treffer kommen vor (Durchgang B bei Auto, Nummeriert, Rookie) → Preisband-Teilung nötig.
- Geschätzter Verbrauch: ca. 300–450 Abfragen je Lauf, also ca. 900 am Tag bei zwei Läufen. Kontingent 5.000.

## Endpreis

- `GET /buy/browse/v1/item/?item_ids=…` (mehrere auf einmal) → **403 Access denied** (eingeschränkte Methode).
- `GET /buy/browse/v1/item/{id}` geht einzeln und liefert auch Minuten nach dem Ende noch den letzten Preis.
- Ein Einzelabruf je beendeter Auktion (mehrere tausend pro Lauf) würde das Tageskontingent sprengen.
  → **Kein Endpreis-Abruf.** Das Archiv zeigt den zuletzt gesehenen Preis, beschriftet als „zuletzt gesehen“.

## football-data.org

- Noch offen: Schlüssel vom Nutzer (Prüfung der Kader aller 7 Ligen folgt, sobald er da ist).
