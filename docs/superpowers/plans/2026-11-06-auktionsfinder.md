# Auktionsfinder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein über GitHub laufender Finder, der eBay.de-Auktionen für Fußball-Sportkarten sucht, Titel einer Spieler-Datenbank zuordnet, jede Auktion dauerhaft archiviert und alles in einer Pages-App mit Dropdown-Filtern zeigt.

**Architecture:** Python-Paket `finder/` (nur Standardbibliothek) läuft in GitHub Actions (Zeitplan 2×/Tag + `workflow_dispatch`), schreibt JSON nach `daten/` und committet. Eine statische App in `web/` (ES-Module, kein Build) liest die JSON-Dateien über die GitHub-API bzw. Pages und schreibt gespeicherte Suchen mit einem Zugangsschlüssel aus `localStorage`.

**Tech Stack:** Python 3.12 + pytest, Vanilla JS (ES-Module) + `node --test`, GitHub Actions, GitHub Pages (Deploy per `actions/deploy-pages`), eBay Browse API, football-data.org v4, Wikidata SPARQL.

**Spec:** `docs/superpowers/specs/2026-11-06-auktionsfinder-design.md`

## Global Constraints

- Python 3.12, **keine Fremdpakete zur Laufzeit** (HTTP über `urllib`); pytest nur zum Testen.
- Web: kein Framework, kein Build-Schritt, alle Texte auf Deutsch, fürs Handy zuerst (ab 360 px Breite ohne waagrechtes Scrollen).
- Geldbeträge als ganze Cent (`int`), Zeiten als ISO-8601 in UTC mit `Z`.
- JSON immer UTF-8, `ensure_ascii=False`, `indent=1`; Schreiben atomar (temporäre Datei + `os.replace`).
- Secrets heißen exakt `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `FOOTBALL_DATA_KEY`; nie im Code, in Logs oder in `daten/`.
- **Es wird nie eine Auktion gelöscht.** Beendet nur, wenn `ende` < jetzt.
- eBay: Marketplace `EBAY_DE`, nur `buyingOptions:{AUCTION}`, `limit=200`, Offset + Limit ≤ 10.000.
- Zeitplan: Cron `0 6,18 * * *` (UTC ≈ 7/19 Uhr MEZ, 8/20 Uhr MESZ).
- Ligen-Codes football-data: `BL1, PL, PD, SA, FL1, DED, PPL`; höchstens 10 Abrufe pro Minute.
- Gruppen-IDs: `bvb-seit-2000`, `bvb-legende`, `fifa-kult`. Kartentyp-IDs: `auto`, `relic`, `nummeriert`, `rookie`, `alle`.
- Spielerlisten aus Wikidata/Codex werden **vor dem Übernehmen dem Nutzer vorgelegt**; Grenzfälle entscheidet er.

## Review Focus

1. Dieselbe Auktion kommt im selben Lauf über zwei Typsuchen (Auto + Relic) → genau ein Eintrag, `typen` vereinigt (Task 5).
2. Saisonangaben wie „Topps 2023/24“ → **nicht** „nummeriert“; „/99“ und „12/99“ schon (Task 3).
3. eBay liefert auf Seite 3 einen Fehler → `laufend.json` und Archiv bleiben byteweise unverändert, `status.json` meldet den Fehler, Exitcode 1 (Task 6).
4. Zwei Spieler mit gleichem Nachnamen (z. B. zwei „Silva“) → Nachname allein trifft keinen von beiden; voller Name trifft (Task 2).
5. App speichert eine Suche, während jemand `suchen.json` geändert hat (HTTP 409) → neu laden, Änderung erneut anwenden, ein zweiter Versuch; die andere Änderung geht nicht verloren (Task 9).

---

## Dateistruktur

```
finder/
  __init__.py
  jsondatei.py      lese_json / schreibe_json (atomar)
  normalisieren.py  vereinheitliche()
  spieler.py        SpielerIndex, baue_index(), uebernehme_entwurf()
  erkennung.py      Erkennung, erkenne()
  ebay.py           EbayClient, zu_auktion()
  suchplan.py       oder_gruppen(), plane_suchen()
  archiv.py         einpflegen(), archiviere()
  suchlauf.py       suchlauf(), main()
  kader.py          importiere_kader(), main()
tools/
  wikidata_bvb.py   Entwurf „BVB seit 2000“ aus Wikidata
  uebernehmen.py    CLI: Entwurf → spieler.json
daten/
  spieler.json  vereine.json  kartentypen.json  suchen.json
  laufend.json  status.json  archiv/index.json  archiv/JJJJ-MM.json
  entwurf/      (Kandidatenlisten zur Prüfung, nicht von der App gelesen)
web/
  index.html  app.css  app.js  filter.js  github.js
  filter.test.mjs  github.test.mjs
tests/          pytest, fixtures/ mit gespeicherten API-Antworten
.github/workflows/  suchlauf.yml  kader.yml  seite.yml
docs/klaerung.md    Ergebnisse von Task 0
README.md           Einrichtung für Nutzer und Freund
```

---

### Task 0: Vorab-Klärung (Spike, kein Produktcode)

Ergebnisse gehen nach `docs/klaerung.md` und bestimmen Konstanten in späteren Tasks. Für eBay-Abrufe lokal den eBay-Schlüssel aus Bisasaldo nehmen (nur nach Zustimmung des Nutzers, nur als Umgebungsvariable, nie committen).

- [ ] **Step 1: Kategorie-ID** für Fußball-Sammelkarten auf EBAY_DE ermitteln (Taxonomy API `get_category_suggestions?q=fussball sammelkarten`, Baum `77`) und mit einer Browse-Suche gegenprüfen. Ergebnis: `KATEGORIE = "<id>"`.
- [ ] **Step 2: Suchsyntax testen:** `(auto, autograph, signed)` vs. Einzelbegriffe (Trefferzahlen vergleichen); ob `/99` im `q` etwas bewirkt; ob Mehrwort-Begriffe in Klammern funktionieren. Ergebnis: endgültige `ebay`-Begriffslisten je Typ (nur Einzelwörter, falls Mehrwort nicht geht).
- [ ] **Step 3: Endpreis:** eine gerade beendete Auktion per `GET /buy/browse/v1/item/get_items_by_item_group` bzw. `/item/?item_ids=` abfragen. Ergebnis: `ENDPREIS_ABRUF = True/False`. Bei `False` ist der Endpreis der zuletzt gesehene Preis, die App beschriftet ihn als „zuletzt gesehen“.
- [ ] **Step 4: football-data.org** (Schlüssel vom Nutzer): `GET /v4/competitions/BL1/teams` liefert `squad` mit Spielern? Für alle 7 Codes prüfen. Bei Lücken: Nutzer fragen, bevor es weitergeht.
- [ ] **Step 5: Trefferzahl je Typ** notieren (entscheidet, ob die Preisband-Teilung aus Task 4 im Alltag greift).
- [ ] **Step 6: Commit** `docs/klaerung.md` – „Klärung eBay/football-data“.

---

### Task 1: Gerüst, JSON-Helfer, Vereinheitlichen

**Files:**
- Create: `pyproject.toml`, `finder/__init__.py`, `finder/jsondatei.py`, `finder/normalisieren.py`, `.gitignore`
- Test: `tests/test_normalisieren.py`, `tests/test_jsondatei.py`

**Interfaces:**
- Produces: `vereinheitliche(text: str) -> str`; `lese_json(pfad: Path, standard)`; `schreibe_json(pfad: Path, daten) -> None`

- [ ] **Step 1: Failing tests**

```python
def test_akzente_und_gross():      assert vereinheitliche("Víctor IBARBO") == "victor ibarbo"
def test_sz_und_umlaut():          assert vereinheitliche("Thomas Müller · Größe") == "thomas muller grosse"
def test_satzzeichen():            assert vereinheitliche("Reus/Haaland-Auto!!") == "reus haaland auto"
def test_leerzeichen():            assert vereinheitliche("  a   b ") == "a b"
def test_lesen_standard(tmp_path): assert lese_json(tmp_path / "fehlt.json", {"x": 1}) == {"x": 1}
def test_schreiben_utf8(tmp_path):
    p = tmp_path / "a" / "b.json"; schreibe_json(p, {"n": "Ü"})
    assert '"Ü"' in p.read_text(encoding="utf-8") and lese_json(p, None) == {"n": "Ü"}
```

- [ ] **Step 2:** `python -m pytest tests -q` → FAIL (Import).
- [ ] **Step 3: Implementieren.** `vereinheitliche`: `casefold`, `ß→ss`, NFKD + Kombinationszeichen entfernen, alles außer `[a-z0-9]` → Leerzeichen, zusammenfassen, strippen. `schreibe_json` legt Ordner an und schreibt atomar.
- [ ] **Step 4:** Tests → PASS.
- [ ] **Step 5: Commit** „Gerüst und Vereinheitlichen“.

---

### Task 2: Spieler-Index

**Files:**
- Create: `finder/spieler.py`, `daten/spieler.json` (Start: `{"zu_haeufig": ["silva","santos","muller","fernandes","rodriguez","garcia","martinez","lopez","gomez","costa","pereira","oliveira","souza","kim","lee","nunez"], "spieler": []}`)
- Test: `tests/test_spieler.py`

**Interfaces:**
- Consumes: `vereinheitliche`
- Produces:
  ```python
  @dataclass(frozen=True)
  class SpielerIndex:
      namen: dict[str, tuple[str, ...]]   # vereinheitlichter Suchname -> Spieler-IDs
      spieler: dict[str, dict]            # id -> Spielereintrag (Format laut Spec)
  def baue_index(daten: dict) -> SpielerIndex          # daten = Inhalt von spieler.json
  def uebernehme_entwurf(daten: dict, entwurf: list[dict], gruppe: str) -> dict
  ```

- [ ] **Step 1: Failing tests**

```python
def test_voller_name_immer():            # "victor ibarbo" -> ("victor-ibarbo",)
def test_eigene_suchnamen():             # suchnamen ["vini jr"] -> Treffer
def test_eindeutiger_nachname():         # nur ein Spieler mit Nachname "haaland" -> "haaland" im Index
def test_doppelter_nachname_nicht():     # zwei "... silva"-Spieler (nicht in zu_haeufig) -> "silva" fehlt, beide Vollnamen da
def test_zu_haeufig_nicht():             # einziger "thomas muller" -> "muller" fehlt (zu_haeufig)
def test_kurzer_nachname_nicht():        # Nachname < 4 Zeichen ("rui") -> fehlt
def test_uebernehmen_ergaenzt_gruppe():  # Entwurf-Spieler mit gleichem vereinheitlichten Namen -> gruppe angehängt, vereine vereinigt, kein Duplikat
def test_uebernehmen_neu():              # unbekannter Spieler -> id = slug(name), quelle "manuell", gruppen [gruppe]
```

- [ ] **Step 2:** → FAIL.
- [ ] **Step 3: Implementieren.** Suchnamen je Spieler = `vereinheitliche(name)` ∪ vereinheitlichte `suchnamen`; Nachname (letztes Wort des vereinheitlichten Namens) zusätzlich nur, wenn er ≥ 4 Zeichen hat, nicht in `zu_haeufig` steht und nur bei genau einem Spieler Nachname ist. `slug` = vereinheitlichter Name mit `-` statt Leerzeichen. Entwurfseinträge: `{"name", "vereine"?, "suchnamen"?}`.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** „Spieler-Index“.

---

### Task 3: Treffererkennung

**Files:**
- Create: `finder/erkennung.py`, `daten/kartentypen.json`, `daten/vereine.json` (Start: nur BVB)
- Test: `tests/test_erkennung.py`

`kartentypen.json`: `{"typen": {"auto": {"name": "Auto", "ebay": [...], "titel": [...]}, ...}, "verdaechtig": ["facsimile","reprint","custom","printed signature","pre print","preprint","replica"]}` mit den Begriffen aus der Spec (Stand nach Task 0). `nummeriert.titel` enthält zusätzlich `numbered`, `nummeriert`; das Muster ist im Code.
`vereine.json`: `{"bvb": {"name": "Borussia Dortmund", "liga": "BL1", "stichwoerter": ["bvb", "borussia dortmund", "dortmund"], "football_data_id": 4}}`.

**Interfaces:**
- Consumes: `SpielerIndex`, `vereinheitliche`
- Produces:
  ```python
  @dataclass
  class Erkennung:
      spieler: list[str]; vereine: list[str]; typen: list[str]; verdaechtig: bool
  def erkenne(titel: str, such_typ: str | None, index: SpielerIndex,
              vereine: dict, kartentypen: dict) -> Erkennung
  ```

- [ ] **Step 1: Failing tests**

```python
def test_spieler_wortgrenze():   # "Topps Reusable sleeve" trifft "reus" nicht; "Marco Reus Auto" trifft
def test_zwei_spieler():         # "Reus Haaland Dual Auto" -> beide, sortiert
def test_verein_ueber_spieler(): # Reus (vereine bvb) -> vereine ["bvb"]
def test_verein_ueber_titel():   # "BVB Topps Auto Unbekannt" -> spieler [], vereine ["bvb"]
def test_typ_aus_suche_und_titel():  # such_typ "auto", Titel "... Auto Patch" -> ["auto", "relic"]
def test_alle_ist_kein_typ():    # such_typ "alle", Titel ohne Stichwort -> typen []
def test_nummeriert():           # "/99", "12/99", "#05/25" -> "nummeriert" in typen
def test_saison_nicht_nummeriert():  # "Topps 2023/24 Base", "2024 / 25" -> nicht
def test_verdaechtig():          # "Reus facsimile auto" -> True; "Reus auto" -> False
```

- [ ] **Step 2:** → FAIL.
- [ ] **Step 3: Implementieren.** Namen/Stichwörter: Treffer, wenn `f" {name} "` in `f" {vereinheitliche(titel)} "`. Nummeriert auf dem **Rohtitel** (klein): `/\s?\d{1,4}\b` nach optionaler Zahl, ausgenommen Saisonmuster `\b(19|20)\d{2}\s?/\s?\d{2}\b`. Listen sortiert und ohne Duplikate.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** „Treffererkennung“.

---

### Task 4: eBay-Client und Suchplan

**Files:**
- Create: `finder/ebay.py`, `finder/suchplan.py`, `daten/suchen.json` (`{"suchen": []}`)
- Test: `tests/test_ebay.py`, `tests/test_suchplan.py`, `tests/fixtures/ebay_seite1.json`, `ebay_seite2.json`, `ebay_ohne_gebot.json`

**Interfaces:**
- Consumes: `Erkennung`, `SpielerIndex`
- Produces:
  ```python
  Http = Callable[[str, str, dict, bytes | None], dict]   # (methode, url, header, body) -> JSON
  class EbayFehler(Exception): ...
  class EbayClient:
      def __init__(self, client_id: str, client_secret: str, http: Http = urllib_http,
                   kategorie: str = KATEGORIE): ...
      abfragen: int
      def suche(self, q: str) -> list[dict]                   # alle Seiten, alle Preisbänder
      def hole_items(self, item_ids: list[str]) -> list[dict] # nur wenn ENDPREIS_ABRUF
  def zu_auktion(summary: dict, erk: Erkennung, jetzt: str) -> dict
  def oder_gruppen(begriffe: list[str], max_len: int = 100) -> list[str]
  @dataclass
  class Suche: q: str; typ: str
  def plane_suchen(kartentypen: dict, suchen: dict, index: SpielerIndex, vereine: dict) -> list[Suche]
  ```

- [ ] **Step 1: Failing tests**

```python
def test_token_einmal_und_header():     # Fake-Http: 1× Token-POST (Basic-Auth, grant client_credentials), Suchaufrufe mit
                                        # Bearer + X-EBAY-C-MARKETPLACE-ID EBAY_DE, filter enthält buyingOptions:{AUCTION}, category_ids
def test_alle_seiten():                 # total 250 -> 2 Aufrufe (offset 0, 200), 250 Ergebnisse, abfragen == 3
def test_preisbaender_ueber_10000():    # total 15000 im Band [0, ∞) -> Teilung in Preisbänder, bis jedes Band ≤ 10000
def test_fehler_wirft():                # Http wirft/Status 500 -> EbayFehler
def test_zu_auktion_mit_gebot():        # currentBidPrice 12.50 -> preis_cent 1250, gebote, versand_cent, ende, bild, url
def test_zu_auktion_ohne_gebot():       # kein currentBidPrice -> price.value; ohne shippingOptions -> versand_cent None
def test_oder_gruppen_grenze():         # 30 Nachnamen -> jede Gruppe "(a, b, …)" ≤ 100 Zeichen, alle Namen genau einmal
def test_plan_typen():                  # je Typ außer "alle" eine Suche "(auto, autograph, …)" typ "auto"
def test_plan_alle_karten():            # gespeicherte Suche typ "alle", verein "bvb" -> Nachnamen der BVB-Spieler als oder_gruppen, typ "alle"
def test_plan_alle_ohne_auswahl():      # typ "alle" ohne spieler/verein/gruppe -> ignoriert
def test_plan_ohne_doppelte():          # zwei Suchen mit gleichem q -> eine Suche
```

- [ ] **Step 2:** → FAIL.
- [ ] **Step 3: Implementieren.** `suche`: Preisband `price:[von..bis],priceCurrency:EUR` nur, wenn geteilt werden muss; Teilung: Band halbieren (Start-Obergrenze 10.000 €), bis `total ≤ 10000` oder Bandbreite < 1 €. `urllib_http` wirft `EbayFehler` bei Status ≥ 400. Token-Endpunkt `https://api.ebay.com/identity/v1/oauth2/token`, Scope `https://api.ebay.com/oauth/api_scope`. `zu_auktion` liefert die Felder aus der Spec mit `status "laufend"`, `zuerst_gesehen = zuletzt_gesehen = jetzt`, `endpreis_cent None`. Für „alle“-Suchen der Suchname je Spieler = Nachname (vereinheitlicht).
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** „eBay-Client und Suchplan“.

---

### Task 5: Archivregeln

**Files:**
- Create: `finder/archiv.py`
- Test: `tests/test_archiv.py`

**Interfaces:**
- Produces:
  ```python
  def einpflegen(laufend: list[dict], gefunden: list[dict], jetzt: str) -> tuple[list[dict], list[dict], int]
      # -> (laufend_neu sortiert nach ende, beendet, anzahl_neu)
  def archiviere(beendet: list[dict], archiv_dir: Path) -> None
  ```

- [ ] **Step 1: Failing tests**

```python
def test_neu():                        # unbekannte item_id -> in laufend, anzahl_neu 1
def test_bekannt_aktualisiert():       # preis/gebote/zuletzt_gesehen neu, zuerst_gesehen bleibt, spieler/typen vereinigt
def test_doppelt_im_lauf():            # gleiche item_id 2× in gefunden (typ auto, relic) -> 1 Eintrag, typen ["auto","relic"]
def test_fehlt_aber_nicht_beendet():   # bekannte Auktion fehlt in gefunden, ende > jetzt -> bleibt laufend, unverändert
def test_beendet_nach_endzeit():       # ende < jetzt -> status "beendet", endpreis_cent = preis_cent, nicht mehr in laufend
def test_archiv_monat(tmp_path):       # beendet mit ende 2026-11-30T23:00Z -> archiv/2026-11.json; index.json listet "2026-11"
def test_archiv_ohne_duplikat(tmp_path): # gleiche item_id 2× archivieren -> 1 Eintrag
def test_archiv_behaelt_alte(tmp_path):  # vorhandene Einträge bleiben erhalten
```

- [ ] **Step 2:** → FAIL.
- [ ] **Step 3: Implementieren.** Monatsdatei `{"auktionen": [...]}`, `index.json` `{"monate": [absteigend]}`.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** „Archivregeln“.

---

### Task 6: Suchlauf

**Files:**
- Create: `finder/suchlauf.py`
- Test: `tests/test_suchlauf.py`

**Interfaces:**
- Consumes: alles aus Task 1–5
- Produces:
  ```python
  def suchlauf(daten: Path, client: EbayClient, jetzt: str) -> dict   # gibt status zurück, schreibt status.json
  def main() -> int    # python -m finder.suchlauf [--daten daten]; liest EBAY_* aus Umgebung; 0 = ok, 1 = Fehler
  ```
  `status.json`: `{"start", "ende", "ok": bool, "fehler": str|null, "gefunden": int, "neu": int, "beendet": int, "abfragen": int}`

- [ ] **Step 1: Failing tests** (Fake-Client mit festen Ergebnissen, `tmp_path` als Datenordner mit Kopien der Startdateien)

```python
def test_lauf_schreibt_laufend_und_status():   # 3 Treffer -> laufend.json 3 Einträge mit erkannten Spielern, status ok, neu 3
def test_lauf_archiviert_beendete():           # vorhandene Auktion mit ende < jetzt -> archiv/JJJJ-MM.json
def test_fehler_laesst_daten_unveraendert():   # Fake wirft EbayFehler bei 2. Suche -> laufend.json + archiv byteweise gleich,
                                               # status ok False mit Fehlertext, main() == 1
def test_fehlende_secrets():                   # ohne EBAY_CLIENT_ID -> main() == 1, status-Fehler "eBay-Schlüssel fehlt"
def test_endpreis_abruf():                     # nur wenn ENDPREIS_ABRUF: hole_items liefert Preis -> endpreis_cent übernommen
```

- [ ] **Step 2:** → FAIL.
- [ ] **Step 3: Implementieren.** Reihenfolge: alles laden → alle Suchen ausführen (in Speicher) → erkennen → `einpflegen` → optional Endpreise → erst dann `laufend.json` + Archiv schreiben → `status.json` immer schreiben. Fehlertexte ohne Secrets.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** „Suchlauf“.

---

### Task 7: Kader-Import

**Files:**
- Create: `finder/kader.py`
- Test: `tests/test_kader.py`, `tests/fixtures/fd_bl1_teams.json`

**Interfaces:**
- Produces:
  ```python
  def importiere_kader(spieler_daten: dict, vereine: dict, liga: str, teams: list[dict], jahr: int) -> tuple[dict, dict]
  def main() -> int    # python -m finder.kader; alle 7 Ligen, 6,5 s Pause je Abruf, Header X-Auth-Token
  ```

- [ ] **Step 1: Failing tests**

```python
def test_neuer_spieler():          # id "fd-<id>", quelle football-data, liga "BL1", vereine [{"verein": slug, "von": jahr, "bis": None}]
def test_neuer_verein():           # unbekanntes Team -> vereine.json-Eintrag mit stichwoerter [vereinheitlicht(shortName), vereinheitlicht(name)]
def test_verein_stichwoerter_bleiben():  # BVB hat eigene Stichwörter -> unverändert
def test_wechsel():                # Spieler jetzt bei anderem Verein -> alter Eintrag bis = jahr, neuer Eintrag
def test_liga_verlassen():         # fd-Spieler der Liga fehlt im Kader -> liga None, Eintrag bleibt
def test_manueller_spieler_ergaenzt():   # Wikidata-Spieler gleichen Namens -> kein Duplikat, Liga/Verein ergänzt, quelle bleibt
def test_fehler_unveraendert():    # main mit Http-Fehler -> spieler.json unverändert, Exitcode 1
```

- [ ] **Step 2:** → FAIL. **Step 3:** implementieren (Team-Zuordnung über `football_data_id`, sonst Slug des Namens). **Step 4:** → PASS.
- [ ] **Step 5: Commit** „Kader-Import“.

---

### Task 8: Workflows und Einrichtungsanleitung

**Files:**
- Create: `.github/workflows/suchlauf.yml`, `.github/workflows/kader.yml`, `.github/workflows/seite.yml`, `README.md`

- [ ] **Step 1: `suchlauf.yml`:** `on: schedule (cron "0 6,18 * * *") + workflow_dispatch`; `concurrency: {group: daten, cancel-in-progress: false}`; Rechte `contents: write, pages: write, id-token: write`. Schritte: checkout → setup-python 3.12 → `python -m pytest -q` → `python -m finder.suchlauf` (mit `continue-on-error`, Ergebnis merken) → Commit „Suchlauf <Zeit>“ von `daten/` mit `git pull --rebase` und bis zu 3 Versuchen (läuft immer, auch bei Fehler, damit `status.json` ankommt) → `_site` aus `web/` + `daten/` (ohne `entwurf/`) → `upload-pages-artifact` → `deploy-pages` (Job-Concurrency `pages`) → Job rot, falls der Suchlauf fehlschlug.
- [ ] **Step 2: `kader.yml`:** `schedule "0 4 1 * *"` + `workflow_dispatch`, gleiche Concurrency-Gruppe `daten`, `python -m finder.kader`, Commit wie oben.
- [ ] **Step 3: `seite.yml`:** bei Push auf `main` mit Pfaden `web/**` → Seite bauen und deployen (Concurrency `pages`).
- [ ] **Step 4: Prüfen:** `actionlint` falls installiert, sonst gegenlesen; die echte Prüfung ist der erste Lauf in Task 12.
- [ ] **Step 5: README.md:** Einrichtung für den Freund (eBay-Entwicklerkonto, Production-Keyset, Ausnahme „Marketplace Account Deletion“) und für den Nutzer (football-data-Schlüssel, Repo, drei Secrets, Pages-Quelle „GitHub Actions“, fein abgestufter Zugangsschlüssel nur für dieses Repo mit *Contents* und *Actions* Lesen+Schreiben, im Browser des Freundes eintragen). Hinweis zur 60-Tage-Pause (die Daten-Commits zählen als Aktivität; falls GitHub den Zeitplan trotzdem abschaltet, in Actions wieder aktivieren).
- [ ] **Step 6: Commit** „Workflows und Einrichtung“.

---

### Task 9: App-Logik (Filter + GitHub-Zugriff)

**Files:**
- Create: `web/filter.js`, `web/github.js`
- Test: `web/filter.test.mjs`, `web/github.test.mjs` (`node --test web/`)

**Interfaces:**
- Produces:
  ```js
  // filter.js
  export const STANDARD = {typ: "alle", liga: null, verein: null, spieler: null, gruppe: null,
                           max_preis_cent: null, ende_in_h: 168, verdaechtige: false, nicht_zugeordnet: false};
  export function filtere(auktionen, f, jetzt /* Date */, spielerById, vereine) // -> sortiert nach ende
  // github.js
  export class GitHub {
    constructor({owner, repo, token, fetch = globalThis.fetch})
    async leseJson(pfad)               // -> {daten, sha}; Accept application/vnd.github.raw+json, ohne token: fetch(pfad) relativ
    async schreibeJson(pfad, daten, sha, nachricht)   // -> neue sha; wirft KonfliktFehler bei 409
    async aendereJson(pfad, aenderung /* daten => daten */, nachricht)  // lesen, ändern, schreiben; bei 409 einmal neu
    async starteSuchlauf()             // POST actions/workflows/suchlauf.yml/dispatches {ref: "main"}
    async letzterLauf()                // -> {status, conclusion, erstellt} aus …/runs?per_page=1
  }
  ```

- [ ] **Step 1: Failing tests**

```js
test("typ filtert", ...)              // typ "auto" -> nur Auktionen mit "auto" in typen; "alle" -> alle
test("verein und liga", ...)          // verein "bvb"; liga "BL1" über Spieler-Liga oder Vereins-Liga
test("gruppe", ...)                   // gruppe "fifa-kult" -> nur mit Spieler in dieser Gruppe
test("max preis", ...)                // preis_cent > max -> raus
test("ende in 24 h", ...)             // ende in 30 h -> raus bei 24, drin bei 168; bereits beendet -> raus
test("ende_in_h null fürs Archiv", ...) // keine Zeitgrenze
test("verdächtige ausgeblendet", ...) // verdaechtig true -> raus, mit Schalter drin
test("nicht zugeordnet", ...)         // nur spieler.length === 0
test("sortiert nach ende", ...)
test("leseJson mit Token", ...)       // Fake-fetch: Header Authorization "Bearer …", raw-Accept; sha aus zweitem Abruf mit json-Accept
test("schreibeJson base64 utf-8", ...)// "Ü" korrekt kodiert (TextEncoder), sha mitgeschickt
test("aendereJson bei 409", ...)      // 1. PUT 409 -> neu lesen (enthält fremde Suche), Änderung erneut, 2. PUT ok, fremde Suche bleibt
test("dispatch", ...)                 // POST-URL und Body {ref:"main"}
```

- [ ] **Step 2:** `node --test web/` → FAIL. **Step 3:** implementieren. **Step 4:** → PASS.
- [ ] **Step 5: Commit** „App-Logik Filter und GitHub“.

---

### Task 10: App-Oberfläche

**Files:**
- Create: `web/index.html`, `web/app.css`, `web/app.js`

**Interfaces:**
- Consumes: `filtere`, `STANDARD`, `GitHub`
- Konstanten in `app.js`: `OWNER = "Dabvud"`, `REPO = "auktionsfinder"`; Schlüssel in `localStorage["auktionsfinder.token"]` (Zugriffe in try/catch).

- [ ] **Step 1: Umsetzen** laut Spec-Abschnitt „App“: Kopfzeile (letzter Lauf aus `status.json`, Fehlerhinweis, Knopf „Jetzt suchen“ → `starteSuchlauf`, alle 15 s `letzterLauf` bis `completed`, dann Daten neu laden), Leiste gespeicherter Suchen (Tippen setzt Filter, „Speichern“ fragt Namen per eigenem Eingabefeld – **kein** `prompt()`, Löschen über kleines Menü, beides per `aendereJson("daten/suchen.json", …)`), Filter-Dropdowns (Optionen aus `kartentypen.json`, `vereine.json`, Gruppen, Ligen; Spieler mit `<input list>`), Reiter „Laufend“/„Archiv“ (Monat aus `archiv/index.json`), Kärtchen laut Spec, Endpreis-Beschriftung je nach `ENDPREIS_ABRUF` („Endpreis“ bzw. „zuletzt gesehen“), Einstellungsdialog für den Schlüssel mit kurzer Anleitung. Ohne Schlüssel sind Speichern und „Jetzt suchen“ ausgegraut. Hell/Dunkel per `prefers-color-scheme`.
- [ ] **Step 2: Lokal prüfen:** `python -m http.server 8020` im Ordner mit `web/` + Beispieldaten (`tests/fixtures/app/`), im Browser bei 390 px und 1280 px: Filter, Reiter, gespeicherte Suche anlegen (mit Fake-Schlüssel gegen ein Test-Repo oder abgefangenem fetch), keine Konsolenfehler, kein waagrechtes Scrollen.
- [ ] **Step 3: Commit** „App-Oberfläche“.

---

### Task 11: Spielerdaten (mit Nutzerprüfung)

**Files:**
- Create: `tools/wikidata_bvb.py`, `tools/uebernehmen.py`, `daten/entwurf/bvb_seit_2000.json`, `daten/entwurf/bvb_legenden.json`, `daten/entwurf/fifa_kult.json`
- Modify: `daten/spieler.json`, `daten/vereine.json`

- [ ] **Step 1: Wikidata:** `tools/wikidata_bvb.py` fragt per SPARQL alle Personen mit `P54` (Mitglied der Sportmannschaft) = Borussia Dortmund (`Q41420`, vorher prüfen) mit Startzeit ≥ 2000 oder Endzeit ≥ 2000 ab (nur Herren-Profikader; Jugend/II. Mannschaft sind eigene Items) und schreibt `{"name", "vereine": [{"verein": "bvb", "von", "bis"}]}` nach `daten/entwurf/bvb_seit_2000.json`.
- [ ] **Step 2: Codex** stellt `bvb_legenden.json` (prägende BVB-Spieler vor 2000) und `fifa_kult.json` (FIFA-Kultspieler wie Ibarbo, gern viele) zusammen, je Eintrag mit kurzer Begründung im Feld `warum`.
- [ ] **Step 3: Nutzer prüft** alle drei Listen (Grenzfälle markiert). Erst nach seinem OK weiter.
- [ ] **Step 4:** `python tools/uebernehmen.py daten/entwurf/<datei> --gruppe <gruppe>` (nutzt `uebernehme_entwurf`) für alle drei; Ergebnis stichprobenartig prüfen (Ibarbo, Reus, Haaland, Lewandowski vorhanden, keine Duplikate).
- [ ] **Step 5:** Erster Kader-Import lokal mit dem football-data-Schlüssel (`python -m finder.kader`), danach `pytest` grün.
- [ ] **Step 6: Commit** „Spielerdaten“.

---

### Task 12: Inbetriebnahme und Abnahme

- [ ] **Step 1:** Mit Nutzerzustimmung GitHub-Repo `Dabvud/auktionsfinder` (öffentlich) anlegen, pushen, Secrets eintragen (Nutzer gibt sie selbst ein oder über `gh secret set` aus einer Eingabe, die nicht im Verlauf landet), Pages-Quelle „GitHub Actions“.
- [ ] **Step 2:** `suchlauf` per `workflow_dispatch` starten → grün, `status.json` ok, `laufend.json` gefüllt, Seite erreichbar unter `https://dabvud.github.io/auktionsfinder/`.
- [ ] **Step 3:** Stichprobe: 10 zufällige Treffer in eBay öffnen – sind es Auktionen, stimmen Spieler/Typ? „Nicht zugeordnet“ durchsehen und auffällige Spieler dem Nutzer vorschlagen.
- [ ] **Step 4:** Browserprüfung im Handyformat: Schlüssel eintragen, Suche „BVB Autos“ speichern, „Jetzt suchen“ bis zum Neuladen, Archiv-Reiter.
- [ ] **Step 5:** Nach dem ersten automatischen Lauf (7 bzw. 19 Uhr) prüfen, dass er lief und committet hat.
