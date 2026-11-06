from base64 import b64decode
from copy import deepcopy
from decimal import Decimal
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import pytest

from finder.ebay import ASPEKT, KATEGORIE, EbayClient, EbayFehler, zu_auktion
from finder.erkennung import Erkennung


def seite(vorlage, elemente, total, offset, url):
    """Die gekürzte Fixture auf eine reale Seite mit limit=200 erweitern."""
    antwort = deepcopy(vorlage)
    antwort.update(itemSummaries=elemente, total=total, limit=200, offset=offset, href=url)
    antwort.pop("next", None)
    if offset + 200 < total:
        teile = urlsplit(url)
        parameter = parse_qs(teile.query)
        parameter["offset"] = [str(offset + 200)]
        antwort["next"] = urlunsplit(teile._replace(query=urlencode(parameter, doseq=True)))
    return antwort


def preis_http(fake_http, vorlage, preise):
    """Ein lokaler Markt: Preisfilter und Pagination werden tatsächlich angewandt."""
    elemente = [{**deepcopy(vorlage["itemSummaries"][0]),
                 "itemId": f"v1|{100000000000 + nr}|0",
                 "currentBidPrice": {"value": preis, "currency": "EUR"}}
                for nr, preis in enumerate(preise)]
    baender = []

    def antwort(methode, url, header, body):
        parameter = parse_qs(urlsplit(url).query)
        offset = int(parameter.get("offset", ["0"])[0])
        limit = int(parameter["limit"][0])
        assert limit == 200
        assert offset + limit <= 10000
        assert len(baender) < 250
        filtertext = parameter["filter"][0]
        assert "buyingOptions:{AUCTION}" in filtertext
        assert "deliveryCountry:DE" in filtertext
        band = re.search(r"price:\[([^.]*(?:\.[0-9]+)?)\.\.([^\]]*)\]", filtertext)
        unten, oben = Decimal("0"), Decimal("Infinity")
        if band:
            unten = Decimal(band[1]) if band[1] else Decimal("0")
            oben = Decimal(band[2]) if band[2] else Decimal("Infinity")
            assert "priceCurrency:EUR" in filtertext
        auswahl = [item for item in elemente if unten <= Decimal(item["currentBidPrice"]["value"]) <= oben]
        baender.append((unten, oben, offset, parameter.get("sort", [None])[0], len(auswahl)))
        return seite(vorlage, auswahl[offset:offset + limit], len(auswahl), offset, url)

    return fake_http(antwort), baender


def test_token_einmal_und_header(fake_http, url_parameter):
    http = fake_http(lambda *args: {"total": 0, "itemSummaries": []})
    client = EbayClient("test-id", "test-secret", http=http)
    assert KATEGORIE == "261328"
    assert ASPEKT == "categoryId:261328,Sportart:{Fußball}"
    assert client.suche("auto", True) == []
    assert client.suche("rookie", False) == []
    token = [a for a in http.aufrufe if a[1].endswith("/oauth2/token")]
    assert len(token) == 1
    methode, url, header, body = token[0]
    assert methode == "POST"
    assert url == "https://api.ebay.com/identity/v1/oauth2/token"
    assert header["Authorization"].split()[0] == "Basic"
    assert b64decode(header["Authorization"].split()[1]).decode() == "test-id:test-secret"
    assert parse_qs(body.decode()) == {
        "grant_type": ["client_credentials"], "scope": ["https://api.ebay.com/oauth/api_scope"],
    }
    assert len(http.suchen) == 2
    for methode, url, header, body in http.suchen:
        parameter = url_parameter(url)
        assert methode == "GET"
        assert urlsplit(url).path == "/buy/browse/v1/item_summary/search"
        assert header["Authorization"] == "Bearer t"
        assert header["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_DE"
        assert parameter["category_ids"] == ["261328"]
        assert parameter["limit"] == ["200"]
        assert "buyingOptions:{AUCTION}" in parameter["filter"][0]
        assert "deliveryCountry:DE" in parameter["filter"][0]
        assert body == None
    assert url_parameter(http.suchen[0][1])["aspect_filter"] == [ASPEKT]
    assert "aspect_filter" not in url_parameter(http.suchen[1][1])
    assert client.abfragen == 3
    assert client.warnungen == []


def test_alle_seiten(fake_http, fixture_json, url_parameter):
    vorlagen = [fixture_json("ebay_seite1.json"), fixture_json("ebay_seite2.json")]
    elemente = [{**deepcopy(vorlagen[0]["itemSummaries"][0]), "itemId": f"v1|{100000000000 + nr}|0"}
                for nr in range(250)]

    def antwort(methode, url, header, body):
        offset = int(url_parameter(url).get("offset", ["0"])[0])
        assert offset in [0, 200]
        return seite(vorlagen[offset // 200], elemente[offset:offset + 200], 250, offset, url)

    http = fake_http(antwort)
    client = EbayClient("id", "secret", http=http)
    treffer = client.suche("auto", True)
    assert treffer == elemente
    assert len(treffer) == 250
    assert [int(url_parameter(a[1]).get("offset", ["0"])[0]) for a in http.suchen] == [0, 200]
    assert client.abfragen == 3


def test_preisbaender_ueber_10000(fake_http, fixture_json):
    # Die untere Hälfte muss erneut geteilt werden; ein Treffer liegt über 10.000 Euro.
    preise = ["100.00"] * 6000 + ["3000.00"] * 5000 + ["7000.00"] * 3999 + ["15000.00"]
    http, baender = preis_http(fake_http, fixture_json("ebay_seite1.json"), preise)
    client = EbayClient("id", "secret", http=http)
    treffer = client.suche("auto", False)
    assert len(treffer) == 15000
    assert {item["itemId"] for item in treffer} == {f"v1|{100000000000 + nr}|0" for nr in range(15000)}
    assert sum(1 for unten, oben, offset, sort, total in baender if total > 10000) >= 2
    assert all(total <= 10000 for unten, oben, offset, sort, total in baender if offset > 0)
    assert client.warnungen == []
    assert client.abfragen == len(http.aufrufe)


def test_abgeschnitten_warnung(fake_http, fixture_json):
    http, baender = preis_http(fake_http, fixture_json("ebay_seite1.json"), ["100.00"] * 10001)
    client = EbayClient("id", "secret", http=http)
    treffer = client.suche("auto", False)
    assert len(treffer) == 10000
    assert {item["itemId"] for item in treffer} == {f"v1|{100000000000 + nr}|0" for nr in range(10000)}
    eng = [(unten, oben, offset, sort) for unten, oben, offset, sort, total in baender
           if oben - unten < 1 and total > 10000]
    assert len(eng) >= 50
    assert {sort for unten, oben, offset, sort in eng if offset > 0} == {"endingSoonest"}
    assert max(offset for unten, oben, offset, sort in eng) == 9800
    assert len(client.warnungen) == 1
    assert "abgeschnitten" in client.warnungen[0].lower()


@pytest.mark.parametrize("fehler", [RuntimeError("HTTP 500"), TimeoutError("Zeitüberschreitung")])
@pytest.mark.parametrize("fehler_offset", [0, 400])
def test_fehler_wirft(fake_http, fixture_json, url_parameter, fehler, fehler_offset):
    vorlage = fixture_json("ebay_seite1.json")

    def antwort(methode, url, header, body):
        offset = int(url_parameter(url).get("offset", ["0"])[0])
        if offset == fehler_offset:
            raise fehler
        elemente = [{**vorlage["itemSummaries"][0], "itemId": f"v1|{100000000000 + nr}|0"}
                    for nr in range(offset, min(offset + 200, 450))]
        return seite(vorlage, elemente, 450, offset, url)

    http = fake_http(antwort)
    client = EbayClient("id", "secret", http=http)
    with pytest.raises(EbayFehler, match=str(fehler)):
        client.suche("auto", True)
    assert [int(url_parameter(a[1]).get("offset", ["0"])[0]) for a in http.suchen] == list(range(0, fehler_offset + 1, 200))


def test_zu_auktion_mit_gebot(fixture_json, jetzt):
    summary = fixture_json("ebay_seite1.json")["itemSummaries"][0]
    erk = Erkennung(spieler=["marco-reus"], vereine=["bvb"], typen=["auto"], verdaechtig=False, fussball=False)
    assert zu_auktion(summary, erk, jetzt) == {
        "item_id": "v1|100000000001|0", "titel": "Topps Marco Reus Auto",
        "bild": "100000000001", "preis_cent": 1250,
        "gebote": 3, "versand_cent": 180,
        "ende": "2026-11-07T12:00:00Z",
        "zuerst_gesehen": jetzt, "zuletzt_gesehen": jetzt, "spieler": ["marco-reus"],
        "vereine": ["bvb"], "typen": ["auto"], "verdaechtig": False,
        "status": "laufend", "endpreis_cent": None,
    }
    # Die echte Browse-Antwort enthält currentBidPrice statt price.
    echt = fixture_json("ebay_echt_beispiel.json")["itemSummaries"][1]
    auktion = zu_auktion(echt, erk, jetzt)
    assert auktion["item_id"] == "v1|377608893769|0"
    assert auktion["preis_cent"] == 1050
    assert auktion["versand_cent"] == 619
    assert auktion["gebote"] == 2
    assert auktion["ende"] == "2026-11-06T20:25:54.000Z"
    assert auktion["bild"] == "9lkAAeSwxrdq28iU"


def test_zu_auktion_ohne_gebot(fixture_json, jetzt):
    erk = Erkennung(spieler=[], vereine=[], typen=[], verdaechtig=False, fussball=False)
    auktion = zu_auktion(fixture_json("ebay_ohne_gebot.json"), erk, jetzt)
    assert auktion["preis_cent"] == 99
    assert auktion["gebote"] == 0
    assert auktion["versand_cent"] == None
    assert auktion["spieler"] == []
    assert auktion["endpreis_cent"] == None


@pytest.mark.parametrize(("url", "erwartet"), [
    ("https://i.ebayimg.com/images/g/AbC-12_~/s-l1600.webp", "AbC-12_~"),
    ("https://i.ebayimg.com/images/g/AbC/s-l500.png", "AbC"),
    ("https://example.com/images/g/AbC/s-l225.jpg", "https://example.com/images/g/AbC/s-l225.jpg"),
    ("https://i.ebayimg.com/reus.jpg", "https://i.ebayimg.com/reus.jpg"),
    ("https://i.ebayimg.com/images/g/AbC/s-l225.jpg?x=1", "https://i.ebayimg.com/images/g/AbC/s-l225.jpg?x=1"),
    ("https://i.ebayimg.com/images/g/AbC/s-lx.jpg", "https://i.ebayimg.com/images/g/AbC/s-lx.jpg"),
    (None, None),
])
def test_zu_auktion_bild(fixture_json, jetzt, url, erwartet):
    summary = fixture_json("ebay_ohne_gebot.json")
    summary["image"] = {"imageUrl": url}
    erk = Erkennung(spieler=[], vereine=[], typen=[], verdaechtig=True, fussball=False)
    auktion = zu_auktion(summary, erk, jetzt)
    assert auktion["bild"] == erwartet
    assert auktion["verdaechtig"] is True
    assert auktion["zuerst_gesehen"] == auktion["zuletzt_gesehen"] == jetzt


@pytest.mark.parametrize("bild", [None, {}])
def test_zu_auktion_ohne_bild(fixture_json, jetzt, bild):
    summary = fixture_json("ebay_ohne_gebot.json")
    summary["image"] = bild
    erk = Erkennung(spieler=[], vereine=[], typen=[], verdaechtig=False, fussball=False)
    assert zu_auktion(summary, erk, jetzt)["bild"] is None
    summary.pop("image")
    assert zu_auktion(summary, erk, jetzt)["bild"] is None
