import { STANDARD, filtere, findeSpieler } from './filter.js';
import { GitHub, repoAusAdresse } from './github.js';

// Jede Kopie der Vorlage arbeitet mit ihrem eigenen Repo; lokal (Test) mit der Vorlage.
const { owner: OWNER, repo: REPO } = repoAusAdresse(location.hostname, location.pathname)
  || { owner: 'Dabvud', repo: 'auktionsfinder' };
const SCHLUESSEL_TOKEN = 'auktionsfinder.token';
const SCHLUESSEL_FILTER = 'auktionsfinder.filter';
const SCHLUESSEL_DAUER = 'auktionsfinder.dauer';
// Vor und nach dem eigentlichen Suchen: Start des Rechners, Speichern, Seite bauen.
const RAHMEN_MS = 90000;
const SEITE = 60;
const ABFRAGE_MS = 15000;

const LIGEN = {
  BL1: 'Bundesliga', PL: 'Premier League', PD: 'LaLiga', SA: 'Serie A',
  FL1: 'Ligue 1', DED: 'Eredivisie', PPL: 'Primeira Liga',
};
const GRUPPEN = { favorit: 'Favoriten', 'bvb-seit-2000': 'BVB seit 2000', 'bvb-legende': 'BVB-Legenden', 'fifa-kult': 'FIFA-Kult' };

const $ = id => document.getElementById(id);
const geld = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' });
const datum = new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

const zustand = {
  gh: null,
  spieler: {},
  spielerNachName: new Map(),
  vereine: {},
  kartentypen: { typen: {} },
  suchen: [],
  favoriten: [],
  laufend: [],
  archiv: [],
  tage: [],
  ansicht: 'laufend',
  filter: { ...STANDARD },
  aktiveSuche: null,
  angezeigt: SEITE,
  sucheLaeuft: false,
};

/* ---------- Speicher im Browser (darf fehlen) ---------- */
function lies(schluessel) {
  try { return localStorage.getItem(schluessel); } catch { return null; }
}
function schreib(schluessel, wert) {
  try {
    if (wert === null) localStorage.removeItem(schluessel); else localStorage.setItem(schluessel, wert);
  } catch { /* privater Modus: einfach weiter */ }
}

/* ---------- Daten laden ---------- */
function neuerClient() {
  zustand.gh = new GitHub({ owner: OWNER, repo: REPO, token: lies(SCHLUESSEL_TOKEN) || undefined });
}

async function json(pfad, standard) {
  try {
    return (await zustand.gh.leseJson(pfad)).daten;
  } catch {
    return standard;
  }
}

async function ladeAlles() {
  const [status, laufend, spieler, vereine, kartentypen, suchen, favoriten, index] = await Promise.all([
    json('daten/status.json', null),
    json('daten/laufend.json', { auktionen: [] }),
    json('daten/spieler.json', { spieler: [] }),
    json('daten/vereine.json', {}),
    json('daten/kartentypen.json', { typen: {} }),
    json('daten/suchen.json', { suchen: [] }),
    json('daten/favoriten.json', { namen: [] }),
    json('daten/archiv/index.json', { tage: [] }),
  ]);
  zustand.laufend = laufend.auktionen || [];
  zustand.spieler = Object.fromEntries((spieler.spieler || []).map(s => [s.id, s]));
  zustand.spielerNachName = new Map((spieler.spieler || []).map(s => [s.name.toLowerCase(), s.id]));
  zustand.vereine = vereine;
  zustand.kartentypen = kartentypen;
  zustand.suchen = suchen.suchen || [];
  zustand.favoriten = favoriten.namen || [];
  markiereFavoriten();
  zustand.tage = index.tage || [];
  zeigeStatus(status);
  baueAuswahlen();
  baueSuchen();
  baueFavoriten();
  setzeFilterfelder();
  if (zustand.ansicht === 'archiv') await ladeArchiv();
  zeichne();
}

async function ladeArchiv() {
  const tag = $('archiv-monat').value || zustand.tage[0];
  zustand.archiv = tag ? ((await json(`daten/archiv/${tag}.json`, { auktionen: [] })).auktionen || []) : [];
}

/* ---------- Kopfzeile ---------- */
function zeigeStatus(status) {
  const text = $('lauf-text');
  text.classList.remove('fehler');
  if (zustand.sucheLaeuft) return;
  if (!status) { text.textContent = 'Noch kein Suchlauf.'; return; }
  const wann = datum.format(new Date(status.ende || status.start));
  if (status.ok) {
    const dauer = Date.parse(status.ende) - Date.parse(status.start);
    if (dauer > 0) schreib(SCHLUESSEL_DAUER, String(dauer + RAHMEN_MS));
    text.textContent = `Letzte Suche: ${wann}, ${status.gefunden} Auktionen, davon ${status.neu} neu.`;
  } else {
    text.textContent = `Letzte Suche ${wann} fehlgeschlagen: ${status.fehler}`;
    text.classList.add('fehler');
  }
}

function aktualisiereKnoepfe() {
  const mitSchluessel = Boolean(lies(SCHLUESSEL_TOKEN));
  $('jetzt-suchen').disabled = !mitSchluessel || zustand.sucheLaeuft;
  $('jetzt-suchen').title = mitSchluessel ? '' : 'Dafür in den Einstellungen einen Zugangsschlüssel eintragen.';
  $('suche-speichern').disabled = !mitSchluessel;
  $('suche-speichern').title = $('jetzt-suchen').title;
}

/** Fortschritt geschätzt aus der Dauer des letzten erfolgreichen Laufs; ohne Vergleichswert nur die Minuten. */
function zeigeFortschritt(startMs) {
  const vergangen = Date.now() - startMs;
  const dauer = Number(lies(SCHLUESSEL_DAUER)) || 0;
  const balken = $('lauf-balken');
  if (dauer > 0) {
    const prozent = Math.min(99, Math.max(1, Math.round(vergangen / dauer * 100)));
    $('lauf-text').textContent = `Suche läuft … ca. ${prozent} %`;
    balken.value = prozent;
    balken.hidden = false;
  } else {
    $('lauf-text').textContent = `Suche läuft seit ${Math.round(vergangen / 60000)} Min …`;
    balken.hidden = true;
  }
}

/** Wartet auf das Ende des Laufs, der ab startMs (ms) gestartet wurde, und lädt dann neu. */
async function verfolgeLauf(startMs) {
  zustand.sucheLaeuft = true;
  aktualisiereKnoepfe();
  $('lauf-text').classList.remove('fehler');
  let laufStart = startMs;
  try {
    for (;;) {
      zeigeFortschritt(laufStart);
      await new Promise(r => setTimeout(r, ABFRAGE_MS));
      const lauf = await zustand.gh.letzterLauf();
      if (lauf && Date.parse(lauf.erstellt) >= startMs - 60000) {
        laufStart = Date.parse(lauf.erstellt);
        if (lauf.status === 'completed') break;
      }
    }
    zustand.sucheLaeuft = false;
    $('lauf-balken').hidden = true;
    await ladeAlles();
  } catch (fehler) {
    zustand.sucheLaeuft = false;
    $('lauf-balken').hidden = true;
    $('lauf-text').textContent = `Stand der Suche nicht abrufbar: ${fehler.message}`;
    $('lauf-text').classList.add('fehler');
  }
  aktualisiereKnoepfe();
}

async function jetztSuchen() {
  const start = Date.now();
  try {
    await zustand.gh.starteSuchlauf();
  } catch (fehler) {
    $('lauf-text').textContent = `Suche konnte nicht gestartet werden: ${fehler.message} Zugangsschlüssel in den Einstellungen prüfen.`;
    $('lauf-text').classList.add('fehler');
    return;
  }
  await verfolgeLauf(start);
}

/** Läuft beim Öffnen schon eine Suche (Zeitplan oder anderes Gerät), deren Fortschritt zeigen. */
async function laufendeSucheZeigen() {
  if (!lies(SCHLUESSEL_TOKEN) || zustand.sucheLaeuft) return;
  try {
    const lauf = await zustand.gh.letzterLauf();
    if (lauf && lauf.status !== 'completed') await verfolgeLauf(Date.parse(lauf.erstellt));
  } catch { /* ohne Verbindung zu GitHub einfach den letzten Stand zeigen */ }
}

/* ---------- Auswahlfelder ---------- */
function option(wert, text) {
  const o = document.createElement('option');
  o.value = wert; o.textContent = text;
  return o;
}

function baueAuswahlen() {
  const typ = $('f-typ');
  typ.replaceChildren(option('alle', 'Alle Karten'),
    ...Object.entries(zustand.kartentypen.typen || {}).map(([id, t]) => option(id, t.name)));

  const ligen = new Set(Object.values(zustand.vereine).map(v => v.liga).filter(Boolean));
  $('f-liga').replaceChildren(option('', 'Alle Ligen'),
    ...Object.keys(LIGEN).filter(l => ligen.has(l)).map(l => option(l, LIGEN[l])));

  baueVereine();

  $('f-gruppe').replaceChildren(option('', 'Alle Spieler'),
    ...Object.entries(GRUPPEN).map(([id, name]) => option(id, name)));

  const namen = Object.values(zustand.spieler).map(s => s.name).sort((a, b) => a.localeCompare(b, 'de'));
  $('spieler-liste').replaceChildren(...namen.map(n => option(n, '')));
}

function baueVereine() {
  const liga = zustand.filter.liga;
  const vereine = Object.entries(zustand.vereine)
    .filter(([, v]) => !liga || v.liga === liga)
    .sort(([, a], [, b]) => a.name.localeCompare(b.name, 'de'));
  $('f-verein').replaceChildren(option('', 'Alle Vereine'), ...vereine.map(([id, v]) => option(id, v.name)));
  $('f-verein').value = zustand.filter.verein || '';
}

function setzeFilterfelder() {
  const f = zustand.filter;
  $('f-typ').value = f.typ;
  $('f-liga').value = f.liga || '';
  baueVereine();
  $('f-gruppe').value = f.gruppe || '';
  $('f-spieler').value = f.spieler ? (zustand.spieler[f.spieler]?.name || '') : '';
  $('f-preis').value = f.max_preis_cent === null ? '' : String(Math.round(f.max_preis_cent / 100));
  $('f-zeit').value = f.ende_in_h === null ? '' : String(f.ende_in_h);
  $('f-verdaechtig').checked = f.verdaechtige;
  $('f-ohne').checked = f.nicht_zugeordnet;
}

function liesFilterfelder() {
  const preis = $('f-preis').value.trim();
  const spielerName = $('f-spieler').value.trim().toLowerCase();
  const zeit = $('f-zeit').value;
  zustand.filter = {
    typ: $('f-typ').value || 'alle',
    liga: $('f-liga').value || null,
    verein: $('f-verein').value || null,
    gruppe: $('f-gruppe').value || null,
    spieler: spielerName ? (zustand.spielerNachName.get(spielerName) || null) : null,
    max_preis_cent: preis === '' ? null : Math.round(Number(preis) * 100),
    ende_in_h: zeit === '' ? null : Number(zeit),
    verdaechtige: $('f-verdaechtig').checked,
    nicht_zugeordnet: $('f-ohne').checked,
  };
  schreib(SCHLUESSEL_FILTER, JSON.stringify(zustand.filter));
}

function zaehleFilter() {
  const f = zustand.filter;
  const n = [f.typ !== 'alle', f.liga, f.verein, f.gruppe, f.spieler, f.max_preis_cent !== null,
    f.verdaechtige, f.nicht_zugeordnet].filter(Boolean).length;
  $('filter-zahl').textContent = n ? `${n} aktiv` : '';
}

/* ---------- Gespeicherte Suchen ---------- */
function alsSuchfilter(f) {
  return { typ: f.typ, liga: f.liga, verein: f.verein, spieler: f.spieler, gruppe: f.gruppe, max_preis: f.max_preis_cent };
}

function baueSuchen() {
  const leiste = $('suchen-leiste');
  if (!zustand.suchen.length) {
    const p = document.createElement('p');
    p.className = 'suchen-leer';
    p.textContent = 'Noch keine gespeicherten Suchen. Filter einstellen und „Als Suche speichern“ tippen.';
    leiste.replaceChildren(p);
    return;
  }
  leiste.replaceChildren(...zustand.suchen.map(suche => {
    const chip = document.createElement('span');
    chip.className = 'suche-chip';
    chip.setAttribute('aria-current', String(zustand.aktiveSuche === suche.id));
    const knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.textContent = suche.name;
    knopf.addEventListener('click', () => wendeSucheAn(suche));
    chip.append(knopf);
    if (lies(SCHLUESSEL_TOKEN)) {
      const weg = document.createElement('button');
      weg.type = 'button';
      weg.className = 'entfernen';
      weg.textContent = '×';
      weg.setAttribute('aria-label', `Suche „${suche.name}“ löschen`);
      weg.addEventListener('click', () => loescheSuche(suche));
      chip.append(weg);
    }
    return chip;
  }));
}

function wendeSucheAn(suche) {
  const f = suche.filter || {};
  zustand.filter = {
    ...STANDARD, ende_in_h: zustand.filter.ende_in_h,
    typ: f.typ || 'alle', liga: f.liga || null, verein: f.verein || null, spieler: f.spieler || null,
    gruppe: f.gruppe || null, max_preis_cent: f.max_preis ?? null,
  };
  zustand.aktiveSuche = suche.id;
  setzeFilterfelder();
  baueSuchen();
  zeichne();
}

function slug(text) {
  return text.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/ß/g, 'ss')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'suche';
}

async function speichereSuche(name) {
  const filter = alsSuchfilter(zustand.filter);
  let id = slug(name);
  try {
    await zustand.gh.aendereJson('daten/suchen.json', daten => {
      const suchen = [...(daten.suchen || [])];
      while (suchen.some(s => s.id === id)) id += '-2';
      suchen.push({ id, name, filter });
      return { ...daten, suchen };
    }, `Suche „${name}“ speichern`);
    zustand.suchen.push({ id, name, filter });
    zustand.aktiveSuche = id;
    baueSuchen();
    $('speichern-form').hidden = true;
  } catch (fehler) {
    $('lauf-text').textContent = `Suche nicht gespeichert: ${fehler.message}`;
    $('lauf-text').classList.add('fehler');
  }
}

async function loescheSuche(suche) {
  try {
    await zustand.gh.aendereJson('daten/suchen.json',
      daten => ({ ...daten, suchen: (daten.suchen || []).filter(s => s.id !== suche.id) }),
      `Suche „${suche.name}“ löschen`);
    zustand.suchen = zustand.suchen.filter(s => s.id !== suche.id);
    if (zustand.aktiveSuche === suche.id) zustand.aktiveSuche = null;
    baueSuchen();
  } catch (fehler) {
    $('lauf-text').textContent = `Suche nicht gelöscht: ${fehler.message}`;
    $('lauf-text').classList.add('fehler');
  }
}

/* ---------- Favoriten ---------- */
function markiereFavoriten() {
  // Gleiche Auflösung wie der Suchlauf (voller Name oder Suchname), damit App und Lauf übereinstimmen.
  const liste = Object.values(zustand.spieler);
  const ids = new Set(zustand.favoriten.map(name => findeSpieler(name, liste)));
  for (const s of liste) {
    s.gruppen = (s.gruppen || []).filter(gruppe => gruppe !== 'favorit');
    if (ids.has(s.id)) s.gruppen.push('favorit');
  }
}

function baueFavoriten() {
  const mitSchluessel = Boolean(lies(SCHLUESSEL_TOKEN));
  const hinweis = $('favorit-hinweis');
  const zugangstext = 'Zum Bearbeiten Zugangsschlüssel in den Einstellungen eintragen.';
  $('favorit-form').hidden = !mitSchluessel;
  if (!mitSchluessel) hinweis.textContent = zugangstext;
  else if (hinweis.textContent === zugangstext) hinweis.textContent = '';

  const leiste = $('favoriten-leiste');
  if (!zustand.favoriten.length) {
    leiste.replaceChildren(element('p', 'suchen-leer', 'Noch keine Favoriten. Namen eingeben und hinzufügen.'));
    return;
  }
  leiste.replaceChildren(...zustand.favoriten.map(name => {
    const id = findeSpieler(name, Object.values(zustand.spieler));
    const chip = element('span', 'suche-chip');
    const knopf = element('button', '', name);
    knopf.type = 'button';
    if (!id) knopf.append(element('small', '', 'neu'));
    knopf.addEventListener('click', () => {
      if (!id) {
        hinweis.textContent = 'Wird beim nächsten Suchlauf angelegt.';
        return;
      }
      zustand.filter.spieler = id;
      zustand.aktiveSuche = null;
      zustand.angezeigt = SEITE;
      setzeFilterfelder();
      $('f-spieler').value = zustand.spieler[id].name;
      liesFilterfelder();
      baueSuchen();
      zeichne();
    });
    chip.append(knopf);
    if (mitSchluessel) {
      const weg = element('button', 'entfernen', '×');
      weg.type = 'button';
      weg.setAttribute('aria-label', `Favorit „${name}“ entfernen`);
      weg.addEventListener('click', () => entferneFavorit(name));
      chip.append(weg);
    }
    return chip;
  }));
}

async function aendereFavoriten(aenderung, nachricht) {
  let geaendert;
  await zustand.gh.aendereJson('daten/favoriten.json', daten => (geaendert = aenderung(daten)), nachricht);
  zustand.favoriten = geaendert.namen;
}

async function speichereFavorit() {
  if (!lies(SCHLUESSEL_TOKEN)) return;
  let name = $('favorit-name').value.trim().replace(/\s+/g, ' ');
  if (!name) return;
  if (zustand.favoriten.some(n => n.toLowerCase() === name.toLowerCase())) {
    $('favorit-hinweis').textContent = 'Steht schon in den Favoriten.';
    return;
  }
  const id = findeSpieler(name, Object.values(zustand.spieler));
  if (id) name = zustand.spieler[id].name;
  try {
    await aendereFavoriten(d => ({
      ...d, namen: [...(d.namen || []).filter(n => n.toLowerCase() !== name.toLowerCase()), name],
    }), `Favorit „${name}“ hinzufügen`);
    $('favorit-name').value = '';
    $('favorit-hinweis').textContent = id ? `${name} ist jetzt Favorit.`
      : `${name} ist neu und wird beim nächsten Suchlauf angelegt und gesucht.`;
    markiereFavoriten();
    baueFavoriten();
    zeichne();
  } catch (fehler) {
    const text = `Favorit nicht gespeichert: ${fehler.message}`;
    $('favorit-hinweis').textContent = text;
    $('lauf-text').textContent = text;
    $('lauf-text').classList.add('fehler');
  }
}

async function entferneFavorit(name) {
  if (!lies(SCHLUESSEL_TOKEN)) return;
  try {
    await aendereFavoriten(d => ({
      ...d, namen: (d.namen || []).filter(n => n.toLowerCase() !== name.toLowerCase()),
    }), `Favorit „${name}“ entfernen`);
    $('favorit-hinweis').textContent = `${name} wurde aus den Favoriten entfernt.`;
    markiereFavoriten();
    baueFavoriten();
    zeichne();
  } catch (fehler) {
    const text = `Favorit nicht entfernt: ${fehler.message}`;
    $('favorit-hinweis').textContent = text;
    $('lauf-text').textContent = text;
    $('lauf-text').classList.add('fehler');
  }
}

/* ---------- Liste ---------- */
function bildUrl(bild) {
  return bild.startsWith('http') ? bild : `https://i.ebayimg.com/images/g/${encodeURIComponent(bild)}/s-l225.jpg`;
}

function ebayUrl(itemId) {
  const nummer = String(itemId).split('|')[1] || String(itemId);
  return `https://www.ebay.de/itm/${encodeURIComponent(nummer)}`;
}

function restzeit(ende, jetzt) {
  const ms = Date.parse(ende) - jetzt;
  if (ms <= 0) return { text: 'beendet', klasse: 'vorbei' };
  const min = Math.floor(ms / 60000);
  const std = Math.floor(min / 60);
  const tage = Math.floor(std / 24);
  if (min < 60) return { text: `${min} Min`, klasse: 'bald' };
  if (std < 24) return { text: `${std} Std ${String(min % 60).padStart(2, '0')}`, klasse: 'bald' };
  return { text: `${tage} Tg ${std % 24} Std`, klasse: '' };
}

function element(tag, klasse, text) {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (text !== undefined) e.textContent = text;
  return e;
}

function karte(a, jetzt) {
  const li = element('li', 'karte');

  const bild = element('div', 'karte-bild');
  if (a.bild) {
    const img = document.createElement('img');
    img.src = bildUrl(a.bild); img.alt = ''; img.loading = 'lazy'; img.decoding = 'async';
    bild.append(img);
  }
  const uhr = restzeit(a.ende, jetzt);
  bild.append(element('span', `uhr ${uhr.klasse}`, uhr.text));
  li.append(bild);

  const text = element('div', 'karte-text');
  const preis = element('p', 'preis');
  preis.style.margin = '0';
  const beendet = a.status === 'beendet' || uhr.klasse === 'vorbei';
  const cent = beendet ? (a.endpreis_cent ?? a.preis_cent) : a.preis_cent;
  preis.append(element('strong', '', geld.format(cent / 100)));
  const zusatz = [];
  if (beendet) zusatz.push('zuletzt gesehen');
  zusatz.push(a.gebote === 1 ? '1 Gebot' : `${a.gebote ?? 0} Gebote`);
  if (a.versand_cent !== null && a.versand_cent !== undefined) {
    zusatz.push(a.versand_cent === 0 ? 'Versand frei' : `+ ${geld.format(a.versand_cent / 100)} Versand`);
  }
  preis.append(element('span', '', zusatz.join(', ')));
  text.append(preis);

  const titel = element('p', 'titel', a.titel);
  titel.title = a.titel;
  text.append(titel);

  const marken = element('ul', 'marken');
  for (const id of a.spieler || []) marken.append(element('li', '', zustand.spieler[id]?.name || id));
  for (const id of a.vereine || []) marken.append(element('li', '', zustand.vereine[id]?.name || id));
  for (const id of a.typen || []) marken.append(element('li', 'typ', zustand.kartentypen.typen?.[id]?.name || id));
  if (a.verdaechtig) marken.append(element('li', 'warnung', 'verdächtig'));
  if (marken.childElementCount) text.append(marken);

  text.append(element('p', 'ende', `Ende ${datum.format(new Date(a.ende))}`));

  const link = element('a', 'karte-link', 'Bei eBay öffnen');
  link.href = ebayUrl(a.item_id); link.target = '_blank'; link.rel = 'noopener noreferrer';
  text.append(link);
  li.append(text);
  return li;
}

function zeichne() {
  zaehleFilter();
  const jetzt = new Date();
  const quelle = zustand.ansicht === 'laufend' ? zustand.laufend : zustand.archiv;
  const filter = zustand.ansicht === 'laufend' ? zustand.filter : { ...zustand.filter, ende_in_h: null };
  let treffer = filtere(quelle, filter, jetzt, zustand.spieler, zustand.vereine);
  if (zustand.ansicht === 'archiv') treffer = treffer.reverse();

  const liste = $('liste');
  if (!treffer.length) {
    const leer = element('li', 'leer', quelle.length
      ? 'Keine Auktion passt zu diesen Filtern. Filter lockern oder zurücksetzen.'
      : (zustand.ansicht === 'laufend' ? 'Noch keine Auktionen gefunden. Nach dem nächsten Suchlauf erscheinen sie hier.'
        : 'Für diesen Tag ist im Archiv noch nichts.'));
    liste.replaceChildren(leer);
  } else {
    liste.replaceChildren(...treffer.slice(0, zustand.angezeigt).map(a => karte(a, jetzt.getTime())));
  }
  $('treffer-text').textContent = treffer.length === 1 ? '1 Auktion' : `${treffer.length} Auktionen`;
  $('mehr').hidden = treffer.length <= zustand.angezeigt;
}

/* ---------- Einstellungen ---------- */
function oeffneEinstellungen() {
  $('token').value = lies(SCHLUESSEL_TOKEN) || '';
  $('token-hinweis').textContent = lies(SCHLUESSEL_TOKEN) ? 'Ein Schlüssel ist gespeichert.' : 'Noch kein Schlüssel gespeichert.';
  $('einstellungen').showModal();
}

async function speichereToken() {
  const token = $('token').value.trim();
  if (!token) { $('token-hinweis').textContent = 'Bitte einen Schlüssel einfügen.'; return; }
  schreib(SCHLUESSEL_TOKEN, token);
  neuerClient();
  baueSuchen();
  baueFavoriten();
  $('token-hinweis').textContent = 'Prüfe Schlüssel …';
  try {
    await zustand.gh.letzterLauf();
    $('einstellungen').close();
    aktualisiereKnoepfe();
    await ladeAlles();
  } catch (fehler) {
    $('token-hinweis').textContent = `Schlüssel funktioniert nicht (${fehler.message}). Rechte „Contents“ und „Actions“ prüfen.`;
    aktualisiereKnoepfe();
  }
}

/* ---------- Start ---------- */
function verdrahte() {
  $('einstellungen-oeffnen').addEventListener('click', oeffneEinstellungen);
  $('einstellungen-schliessen').addEventListener('click', () => $('einstellungen').close());
  $('token-speichern').addEventListener('click', speichereToken);
  $('token-entfernen').addEventListener('click', () => {
    schreib(SCHLUESSEL_TOKEN, null);
    neuerClient();
    $('token').value = '';
    $('token-hinweis').textContent = 'Schlüssel entfernt.';
    aktualisiereKnoepfe();
    baueSuchen();
    baueFavoriten();
  });
  $('jetzt-suchen').addEventListener('click', jetztSuchen);
  $('favorit-form').addEventListener('submit', e => {
    e.preventDefault();
    speichereFavorit();
  });

  for (const id of ['f-typ', 'f-liga', 'f-verein', 'f-gruppe', 'f-zeit', 'f-verdaechtig', 'f-ohne']) {
    $(id).addEventListener('change', () => {
      liesFilterfelder();
      if (id === 'f-liga') baueVereine();
      zustand.aktiveSuche = null; zustand.angezeigt = SEITE;
      baueSuchen(); zeichne();
    });
  }
  for (const id of ['f-spieler', 'f-preis']) {
    $(id).addEventListener('input', () => {
      liesFilterfelder(); zustand.aktiveSuche = null; zustand.angezeigt = SEITE; baueSuchen(); zeichne();
    });
  }
  $('filter-zuruecksetzen').addEventListener('click', () => {
    zustand.filter = { ...STANDARD }; zustand.aktiveSuche = null;
    schreib(SCHLUESSEL_FILTER, null);
    setzeFilterfelder(); baueSuchen(); zeichne();
  });

  $('suche-speichern').addEventListener('click', () => {
    $('speichern-form').hidden = false;
    $('speichern-name').focus();
  });
  $('speichern-abbrechen').addEventListener('click', () => { $('speichern-form').hidden = true; });
  $('speichern-form').addEventListener('submit', e => {
    e.preventDefault();
    const name = $('speichern-name').value.trim();
    if (name) speichereSuche(name);
  });

  const reiter = async ansicht => {
    zustand.ansicht = ansicht; zustand.angezeigt = SEITE;
    $('reiter-laufend').setAttribute('aria-pressed', String(ansicht === 'laufend'));
    $('reiter-archiv').setAttribute('aria-pressed', String(ansicht === 'archiv'));
    $('archiv-monat').hidden = ansicht !== 'archiv';
    $('f-zeit-label').hidden = ansicht === 'archiv';
    if (ansicht === 'archiv') {
      const monat = $('archiv-monat');
      if (!monat.options.length) {
        monat.replaceChildren(...zustand.tage.map(t => option(t,
          new Date(`${t}T12:00:00Z`).toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' }))));
      }
      await ladeArchiv();
    }
    zeichne();
  };
  $('reiter-laufend').addEventListener('click', () => reiter('laufend'));
  $('reiter-archiv').addEventListener('click', () => reiter('archiv'));
  $('archiv-monat').addEventListener('change', async () => { await ladeArchiv(); zeichne(); });
  $('mehr').addEventListener('click', () => { zustand.angezeigt += SEITE; zeichne(); });
}

function start() {
  try {
    const gemerkt = JSON.parse(lies(SCHLUESSEL_FILTER) || 'null');
    if (gemerkt) zustand.filter = { ...STANDARD, ...gemerkt };
  } catch { /* alter oder kaputter Eintrag */ }
  if (window.matchMedia('(max-width: 640px)').matches) $('filter-box').open = false;
  neuerClient();
  verdrahte();
  aktualisiereKnoepfe();
  ladeAlles().then(laufendeSucheZeigen);
}

start();
