/** Standardfilter für laufende Auktionen der nächsten sieben Tage. */
export const STANDARD = {
  typ: 'alle',
  liga: null,
  verein: null,
  spieler: null,
  gruppe: null,
  max_preis_cent: null,
  ende_in_h: 168,
  verdaechtige: false,
  nicht_zugeordnet: false,
  standort: null,
  text: '',
  max_auflage: null,
  gebote: null,
  preis_mit_versand: false,
  nur_neue: false,
  sortierung: 'ende',
};

/** Kleinste Auflage aus dem Titel ("12/25" → 25, "1/1" → 1); Saisonangaben wie in finder/erkennung.py ignoriert. */
export function auflage(titel) {
  const ohneSaison = titel
    .replace(/\b(?:19|20)\d{2}\s*\/\s*(?:(?:19|20)\d{2}|\d{2})\b/g, ' ')
    .replace(/\b(\d{2})\s*\/\s*(\d{2})\b/g, (ganz, a, b) => ((Number(a) + 1) % 100 === Number(b) ? ' ' : ganz));
  const zahlen = [...ohneSaison.matchAll(/\/\s*(\d{1,4})\b/g)].map(m => Number(m[1])).filter(n => n > 0);
  return zahlen.length ? Math.min(...zahlen) : null;
}

const EU = new Set('AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK'.split(' '));
const gesamt = (auktion, mitVersand) => auktion.preis_cent + (mitVersand ? auktion.versand_cent || 0 : 0);
const SORTIERUNG = {
  ende: (a, b) => Date.parse(a.ende) - Date.parse(b.ende),
  neu: (a, b) => Date.parse(b.zuerst_gesehen) - Date.parse(a.zuerst_gesehen),
};

/**
 * Filtert und sortiert Auktionen. neuSeit (ISO-Zeit oder null): Stichtag für "nur neue";
 * ohne Stichtag (erster Besuch) wirkt der Filter nicht.
 */
export function filtere(auktionen, filter, jetzt, spielerNachId, vereine, neuSeit = null) {
  const auswahl = { ...STANDARD, ...filter };
  const jetztMs = jetzt.getTime();
  const zeitgrenze = jetztMs + auswahl.ende_in_h * 60 * 60 * 1000;
  const woerter = vereinheitliche(auswahl.text || '').split(' ').filter(Boolean);
  const stichtag = auswahl.nur_neue && neuSeit ? Date.parse(neuSeit) : null;

  return auktionen.filter(auktion => {
    if (auswahl.typ !== 'alle' && !auktion.typen.includes(auswahl.typ)) return false;
    if (auswahl.verein && !auktion.vereine.includes(auswahl.verein)) return false;
    if (auswahl.spieler && !auktion.spieler.includes(auswahl.spieler)) return false;
    if (auswahl.nicht_zugeordnet && auktion.spieler.length !== 0) return false;
    if (!auswahl.verdaechtige && auktion.verdaechtig) return false;

    if (auswahl.standort === 'DE' && auktion.land !== 'DE') return false;
    if (auswahl.standort === 'EU' && !EU.has(auktion.land)) return false;
    if (auswahl.gebote === 'ohne' && auktion.gebote > 0) return false;
    if (auswahl.gebote === 'mit' && !(auktion.gebote > 0)) return false;
    if (stichtag !== null && !(Date.parse(auktion.zuerst_gesehen) > stichtag)) return false;
    if (woerter.length) {
      const titel = ` ${vereinheitliche(auktion.titel)} `;
      if (!woerter.every(wort => titel.includes(wort))) return false;
    }
    if (auswahl.max_auflage !== null) {
      const n = auflage(auktion.titel);
      if (n === null || n > auswahl.max_auflage) return false;
    }

    if (auswahl.max_preis_cent !== null && gesamt(auktion, auswahl.preis_mit_versand) > auswahl.max_preis_cent) {
      return false;
    }

    if (auswahl.ende_in_h !== null) {
      const ende = Date.parse(auktion.ende);
      if (!(ende >= jetztMs && ende <= zeitgrenze)) return false;
    }

    if (auswahl.gruppe && !auktion.spieler.some(
      kennung => spielerNachId[kennung]?.gruppen?.includes(auswahl.gruppe),
    )) return false;

    if (auswahl.liga) {
      const spielerPasst = auktion.spieler.some(
        kennung => spielerNachId[kennung]?.liga === auswahl.liga,
      );
      const vereinPasst = auktion.vereine.some(
        kennung => vereine[kennung]?.liga === auswahl.liga,
      );
      if (!spielerPasst && !vereinPasst) return false;
    }

    return true;
  }).sort(auswahl.sortierung === 'preis'
    ? (a, b) => gesamt(a, auswahl.preis_mit_versand) - gesamt(b, auswahl.preis_mit_versand)
    : SORTIERUNG[auswahl.sortierung] || SORTIERUNG.ende);
}

/** Wie finder/normalisieren.py: Kleinschreibung, ohne Akzente, nur a-z und 0-9. */
export function vereinheitliche(text) {
  return text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ').trim();
}

/** Spieler-ID zu einem eingegebenen Namen, wie der Suchlauf es auflöst; mehrdeutig oder unbekannt → null. */
export function findeSpieler(name, spielerListe) {
  const gesucht = vereinheitliche(name);
  if (!gesucht) return null;
  const treffer = spielerListe.filter(s =>
    [s.name, ...(s.suchnamen || [])].some(n => vereinheitliche(n) === gesucht));
  return treffer.length === 1 ? treffer[0].id : null;
}
