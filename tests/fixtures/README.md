# API-Fixtures

- `ebay_echt_beispiel.json`: vorhandene, unveränderte echte Browse-Antwort aus Task 0.
- `ebay_seite1.json`, `ebay_seite2.json`: synthetische, gekürzte Browse-Antworten mit insgesamt drei Auktionen; die Seiten haben `limit=2`. Die Paginationstests erweitern diese Vorlagen im Speicher auf 200 und 50 Einträge (`total=250`, `limit=200`).
- `ebay_ohne_gebot.json`: synthetisches Browse-Summary ohne `currentBidPrice` und ohne Versandangabe; der Startpreis steht in `price`.
- `fd_bl1_teams.json`: synthetische, gekürzte football-data-v4-Antwort. Kader stehen unter `teams[*].squad`, Spieler-IDs sind Testwerte. Dies ist kein Abruf eines aktuellen Kaders.

Preisbandtests erzeugen weitere Summaries im Speicher und wenden Preisfilter und Offsets im Fake tatsächlich an. Alle Tests laufen ohne Netz; ein gemeinsamer Helfer blockiert versehentliche echte Abrufe. Die produktiven Startdaten bleiben frei von Testspielern und Testauktionen.
