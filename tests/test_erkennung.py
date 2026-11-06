import pytest

from finder.erkennung import erkenne
from finder.spieler import baue_index


@pytest.fixture
def erkennung(spieler_daten, vereine, kartentypen):
    index = baue_index(spieler_daten)
    return lambda titel, typ=None: erkenne(titel, typ, index, vereine, kartentypen)


def test_spieler_wortgrenze(erkennung):
    assert erkennung("Topps Reusable sleeve").spieler == []
    assert erkennung("Marco Reus Auto").spieler == ["marco-reus"]


def test_zwei_spieler(erkennung):
    assert erkennung("Reus Haaland Dual Auto").spieler == ["erling-haaland", "marco-reus"]


def test_verein_ueber_spieler(erkennung):
    assert erkennung("Reus Base").vereine == ["bvb"]


def test_verein_ueber_titel(erkennung):
    erk = erkennung("BVB Topps Auto Unbekannt")
    assert erk.spieler == []
    assert erk.vereine == ["bvb"]


@pytest.mark.parametrize(("titel", "typ", "erwartet"), [
    ("Reus Auto Patch", "auto", ["auto", "relic"]),
    ("Reus Base", "auto", ["auto"]),
    ("Reus Base", "relic", ["relic"]),
    ("Reus Base", "rookie", ["rookie"]),
    ("Reus Base", "nummeriert", []),
    ("Reus numbered", "nummeriert", ["nummeriert"]),
    ("Reus nummeriert", None, ["nummeriert"]),
])
def test_typ_aus_suche_und_titel(erkennung, titel, typ, erwartet):
    assert erkennung(titel, typ).typen == erwartet


def test_alle_ist_kein_typ(erkennung):
    assert erkennung("Topps Reus Base", "alle").typen == []


@pytest.mark.parametrize("nummer", ["/99", "12/99", "#05/25", "/ 199", "/9999"])
def test_nummeriert(erkennung, nummer):
    assert erkennung(f"Topps Reus {nummer}").typen == ["nummeriert"]


@pytest.mark.parametrize("titel", ["Topps 2023/24 Base", "2024 / 25", "Topps 1999/00 Base", "Topps Chrome 23/24", "Topps 2023/2024", "Panini 99/00"])
def test_saison_nicht_nummeriert(erkennung, titel):
    assert erkennung(titel, "nummeriert").typen == []
    assert erkennung(titel + " Reus 12/99").typen == ["nummeriert"]


@pytest.mark.parametrize("wort", ["facsimile", "reprint", "custom", "printed signature", "pre-print", "preprint", "replica"])
def test_verdaechtig(erkennung, wort):
    assert erkennung(f"Reus {wort} auto").verdaechtig == True
    assert erkennung("Reus auto").verdaechtig == False


@pytest.mark.parametrize(("titel", "erwartet"), [
    ("Topps Bundesliga Auto", True), ("UEFA Champions League Base", True),
    ("Premier League Rookie", True), ("Match Attax Fußball", True),
    ("Topps Soccer Auto", True), ("Topps Basketball Auto", False),
    ("Bundesligakarte Base", False),
])
def test_fussball(erkennung, titel, erwartet):
    assert erkennung(titel).fussball == erwartet
