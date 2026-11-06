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
};

/** Filtert Auktionen und gibt sie nach Endzeit aufsteigend sortiert zurück. */
export function filtere(auktionen, filter, jetzt, spielerNachId, vereine) {
  const auswahl = { ...STANDARD, ...filter };
  const jetztMs = jetzt.getTime();
  const zeitgrenze = jetztMs + auswahl.ende_in_h * 60 * 60 * 1000;

  return auktionen.filter(auktion => {
    if (auswahl.typ !== 'alle' && !auktion.typen.includes(auswahl.typ)) return false;
    if (auswahl.verein && !auktion.vereine.includes(auswahl.verein)) return false;
    if (auswahl.spieler && !auktion.spieler.includes(auswahl.spieler)) return false;
    if (auswahl.nicht_zugeordnet && auktion.spieler.length !== 0) return false;
    if (!auswahl.verdaechtige && auktion.verdaechtig) return false;

    if (auswahl.max_preis_cent !== null && auktion.preis_cent > auswahl.max_preis_cent) {
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
  }).sort((erste, zweite) => Date.parse(erste.ende) - Date.parse(zweite.ende));
}
