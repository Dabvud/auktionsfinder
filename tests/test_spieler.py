from finder.spieler import baue_index, pflege_favoriten, uebernehme_entwurf


def test_voller_name_immer(spieler_fabrik):
    spieler = spieler_fabrik("victor-ibarbo", "Víctor Ibarbo")
    index = baue_index({"zu_haeufig": [], "spieler": [spieler]})
    assert index.namen["victor ibarbo"] == ("victor-ibarbo",)
    assert index.spieler == {"victor-ibarbo": spieler}


def test_eigene_suchnamen(spieler_fabrik):
    spieler = spieler_fabrik("vinicius-junior", "Vinícius Júnior", suchnamen=["Vini Jr"])
    index = baue_index({"zu_haeufig": [], "spieler": [spieler]})
    assert index.namen["vini jr"] == ("vinicius-junior",)
    assert index.namen["vinicius junior"] == ("vinicius-junior",)


def test_nachname_allein_nur_als_suchname(spieler_fabrik):
    # Echter Lauf: ~90 % der reinen Nachnamen-Treffer waren falsch (Bukayo Saka -> "Kosi Saka").
    index = baue_index({"zu_haeufig": [], "spieler": [
        spieler_fabrik("erling-haaland", "Erling Haaland", suchnamen=["haaland"]),
        spieler_fabrik("kosi-saka", "Kosi Saka"),
    ]})
    assert index.namen["haaland"] == ("erling-haaland",)
    assert "saka" not in index.namen
    assert index.namen["kosi saka"] == ("kosi-saka",)


def test_doppelter_nachname_nicht(spieler_fabrik):
    index = baue_index({"zu_haeufig": [], "spieler": [
        spieler_fabrik("bernardo-silva", "Bernardo Silva"),
        spieler_fabrik("thiago-silva", "Thiago Silva"),
    ]})
    assert "silva" not in index.namen
    assert index.namen["bernardo silva"] == ("bernardo-silva",)
    assert index.namen["thiago silva"] == ("thiago-silva",)


def test_zu_haeufig_nicht(spieler_fabrik):
    index = baue_index({"zu_haeufig": ["muller"], "spieler": [
        spieler_fabrik("thomas-muller", "Thomas Müller"),
    ]})
    assert "muller" not in index.namen
    assert index.namen["thomas muller"] == ("thomas-muller",)


def test_kurzer_nachname_nicht(spieler_fabrik):
    index = baue_index({"zu_haeufig": [], "spieler": [
        spieler_fabrik("mario-rui", "Mário Rui"),
    ]})
    assert "rui" not in index.namen
    assert index.namen["mario rui"] == ("mario-rui",)


def test_uebernehmen_ergaenzt_gruppe(spieler_fabrik):
    bvb = {"verein": "bvb", "von": 2012, "bis": 2024}
    gladbach = {"verein": "gladbach", "von": 2009, "bis": 2012}
    daten = {"zu_haeufig": ["silva"], "spieler": [spieler_fabrik(
        name="Marco Réus", gruppen=["bvb-seit-2000"], quelle="wikidata",
    )]}
    neu = uebernehme_entwurf(daten, [{"name": "MARCO REUS", "vereine": [bvb, gladbach]}], "bvb-legende")
    assert len(neu["spieler"]) == 1
    spieler = neu["spieler"][0]
    assert spieler["id"] == "marco-reus"
    assert sorted(spieler["gruppen"]) == ["bvb-legende", "bvb-seit-2000"]
    assert sorted(spieler["vereine"], key=lambda v: v["von"]) == [gladbach, bvb]
    assert spieler["quelle"] == "wikidata"
    assert neu["zu_haeufig"] == ["silva"]


def test_uebernehmen_neu():
    neu = uebernehme_entwurf({"zu_haeufig": [], "spieler": []}, [{
        "name": "Víctor Ibarbo", "suchnamen": ["ibarbo"],
        "vereine": [{"verein": "cagliari", "von": 2011, "bis": 2015}],
    }], "fifa-kult")
    assert neu == {"zu_haeufig": [], "spieler": [{
        "id": "victor-ibarbo", "name": "Víctor Ibarbo", "suchnamen": ["ibarbo"],
        "vereine": [{"verein": "cagliari", "von": 2011, "bis": 2015}],
        "liga": None, "gruppen": ["fifa-kult"], "quelle": "manuell",
    }]}


def test_favoriten_markieren_anlegen_und_entfernen(spieler_daten):
    spieler_daten["spieler"][1]["gruppen"].append("favorit")
    neu = pflege_favoriten(spieler_daten, ["  marco   REUS ", "Ibarbo", "Haaland", "Ibarbo", ""])
    nach_id = {s["id"]: s for s in neu["spieler"]}
    # voller Name (egal wie geschrieben) und Suchname treffen den vorhandenen Spieler
    assert "favorit" in nach_id["marco-reus"]["gruppen"]
    assert "favorit" in nach_id["erling-haaland"]["gruppen"]
    assert nach_id["ibarbo"] == {"id": "ibarbo", "name": "Ibarbo", "suchnamen": [], "vereine": [],
                                 "liga": None, "gruppen": ["favorit"], "quelle": "favorit"}
    assert len(neu["spieler"]) == 3
    assert "favorit" not in spieler_daten["spieler"][0]["gruppen"]  # Eingabe unverändert

    weniger = pflege_favoriten(neu, ["Ibarbo"])
    nach_id = {s["id"]: s for s in weniger["spieler"]}
    assert "favorit" not in nach_id["marco-reus"]["gruppen"]
    assert nach_id["erling-haaland"]["gruppen"] == ["fifa-kult"]
    assert len(weniger["spieler"]) == 3  # angelegte Einträge bleiben, alte Auktionen verweisen darauf


def test_favorit_ohne_buchstaben_wird_ignoriert(spieler_daten):
    neu = pflege_favoriten(spieler_daten, ["!!!", " - "])
    assert neu["spieler"] == spieler_daten["spieler"]
