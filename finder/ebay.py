"""Browse-API mit Token, Seitenabruf und vollstaendigen Preisbaendern."""

from base64 import b64encode
from collections.abc import Callable
from decimal import Decimal, ROUND_HALF_UP
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .erkennung import Erkennung

KATEGORIE = "261328"
ASPEKT = "categoryId:261328,Sportart:{Fußball}"
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SUCHE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
Http = Callable[[str, str, dict, bytes | None], dict]


class EbayFehler(Exception):
    """Ein eBay-Abruf konnte nicht abgeschlossen werden."""


def urllib_http(methode: str, url: str, header: dict, body: bytes | None) -> dict:
    """Netzfehler und HTTP 5xx genau einmal wiederholen."""
    return _urllib_http(methode, url, header, body, lambda: None)


def _urllib_http(methode, url, header, body, zaehle) -> dict:
    """Jeden tatsaechlichen HTTP-Versuch einzeln zaehlen."""
    for versuch in range(2):
        zaehle()
        try:
            anfrage = urllib.request.Request(url, data=body, headers=header, method=methode)
            with urllib.request.urlopen(anfrage, timeout=30) as antwort:
                status = antwort.status
                if status >= 400:
                    raise urllib.error.HTTPError(url, status, "HTTP-Fehler", {}, None)
                return json.load(antwort)
        except urllib.error.HTTPError as fehler:
            if versuch == 0 and 500 <= fehler.code < 600:
                continue
            raise EbayFehler(f"eBay HTTP {fehler.code}") from None
        except (urllib.error.URLError, OSError):
            if versuch == 0:
                continue
            raise EbayFehler("eBay-Netzfehler oder Zeitueberschreitung") from None
        except (ValueError, UnicodeError):
            raise EbayFehler("Ungueltige eBay-Antwort") from None


class EbayClient:
    """Alle Treffer abrufen; OAuth-Token bis zum Ablauf wiederverwenden."""

    def __init__(self, client_id: str, client_secret: str, http: Http = urllib_http,
                 kategorie: str = KATEGORIE):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http
        self._kategorie = kategorie
        self._token = ""
        self._ablauf = 0.0
        self.abfragen = 0
        self.warnungen: list[str] = []

    def _abruf(self, methode: str, url: str, header: dict, body: bytes | None = None) -> dict:
        try:
            if self._http is urllib_http:
                antwort = _urllib_http(methode, url, header, body, self._zaehle)
            else:
                self._zaehle()
                antwort = self._http(methode, url, header, body)
            if not isinstance(antwort, dict):
                raise EbayFehler("Ungueltige eBay-Antwort")
            if antwort.get("errors"):
                raise EbayFehler("eBay hat die Anfrage abgelehnt")
            return antwort
        except Exception as fehler:
            text = str(fehler)
            basic = b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
            for geheim in sorted([self._client_id, self._client_secret, self._token, basic], key=len, reverse=True):
                if geheim:
                    if len(geheim) < 4:
                        text = re.sub(r"(?<!\w)" + re.escape(geheim) + r"(?!\w)", "[entfernt]", text)
                    else:
                        text = text.replace(geheim, "[entfernt]")
            raise EbayFehler(text or "eBay-Abruf fehlgeschlagen") from None

    def _zaehle(self) -> None:
        self.abfragen += 1

    def _header(self) -> dict:
        if not self._token or time.monotonic() >= self._ablauf:
            basic = b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
            body = urllib.parse.urlencode({
                "grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope",
            }).encode()
            antwort = self._abruf("POST", TOKEN_URL, {
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            }, body)
            try:
                self._token = antwort["access_token"]
                self._ablauf = time.monotonic() + float(antwort["expires_in"])
            except (KeyError, TypeError, ValueError):
                raise EbayFehler("Ungueltige eBay-Tokenantwort") from None
        return {"Authorization": f"Bearer {self._token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE"}

    def _seite(self, q: str, aspekt: bool, band, offset=0, sort=None) -> dict:
        filtertext = "buyingOptions:{AUCTION},deliveryCountry:DE"
        if band is not None:
            unten, oben = band
            grenze = "" if oben is None else f"{Decimal(oben) / 100:.2f}"
            filtertext += f",price:[{Decimal(unten) / 100:.2f}..{grenze}],priceCurrency:EUR"
        parameter = {"q": q, "category_ids": self._kategorie, "limit": 200,
                     "offset": offset, "filter": filtertext}
        if aspekt:
            parameter["aspect_filter"] = ASPEKT
        if sort:
            parameter["sort"] = sort
        return self._abruf("GET", SUCHE_URL + "?" + urllib.parse.urlencode(parameter), self._header())

    def _band(self, q: str, aspekt: bool, band=None) -> list[dict]:
        erste = self._seite(q, aspekt, band)
        total = int(erste.get("total", 0))
        sort = None
        if total > 10000:
            unten, oben = (0, None) if band is None else band
            if oben is None or oben - unten >= 100:
                # Cent-Grenzen verhindern Ueberlappungen; das obere Band bleibt offen.
                mitte = max(1000000, unten * 2) if oben is None else (unten + oben + 1) // 2
                return self._band(q, aspekt, (unten, mitte - 1)) + self._band(q, aspekt, (mitte, oben))
            self.warnungen.append("Preisband mit mehr als 10000 Treffern abgeschnitten")
            sort = "endingSoonest"
            erste = self._seite(q, aspekt, band, sort=sort)
        treffer = list(erste.get("itemSummaries", []))
        for offset in range(200, min(total, 10000), 200):
            seite = self._seite(q, aspekt, band, offset=offset, sort=sort)
            treffer.extend(seite.get("itemSummaries", []))
        return treffer

    def suche(self, q: str, aspekt: bool) -> list[dict]:
        """Alle Seiten in disjunkten Preisbaendern durchsuchen."""
        treffer = self._band(q, aspekt)
        return list({eintrag["itemId"]: eintrag for eintrag in treffer}.values())


def _cent(geld: dict | None) -> int | None:
    """Dezimale API-Geldbetraege ohne Gleitkommafehler umrechnen."""
    if not geld or geld.get("value") is None:
        return None
    return int((Decimal(str(geld["value"])) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def zu_auktion(summary: dict, erk: Erkennung, jetzt: str) -> dict:
    """Ein Browse-Angebot in das lokale Auktionsformat uebertragen."""
    preis = summary.get("currentBidPrice") or summary.get("price") or {}
    versand = next(iter(summary.get("shippingOptions") or []), {})
    bild = (summary.get("image") or {}).get("imageUrl")
    if bild:
        treffer = re.fullmatch(r"https://i\.ebayimg\.com/images/g/([^/?#]+)/s-l[0-9]+\.[A-Za-z0-9]+", bild)
        if treffer:
            bild = treffer[1]
    return {
        "item_id": summary["itemId"], "titel": summary["title"],
        "bild": bild, "preis_cent": _cent(preis), "gebote": summary.get("bidCount", 0),
        "versand_cent": _cent(versand.get("shippingCost")),
        "ende": summary.get("itemEndDate"),
        "zuerst_gesehen": jetzt, "zuletzt_gesehen": jetzt,
        "spieler": list(erk.spieler), "vereine": list(erk.vereine), "typen": list(erk.typen),
        "verdaechtig": erk.verdaechtig, "status": "laufend", "endpreis_cent": None,
    }
