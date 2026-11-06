import test from 'node:test';
import assert from 'node:assert/strict';
import { STANDARD, filtere, findeSpieler, auflage } from './filter.js';

const jetzt = new Date('2026-11-06T12:00:00Z');
const spielerById = {
  'marco-reus': {
    name: 'Marco Reus', liga: 'MLS', gruppen: ['bvb-seit-2000'],
    vereine: [{ verein: 'bvb', von: 2012, bis: 2024 }],
  },
  'jamal-musiala': {
    name: 'Jamal Musiala', liga: 'BL1', gruppen: [],
    vereine: [{ verein: 'bayern', von: 2020, bis: null }],
  },
  'victor-ibarbo': {
    name: 'Víctor Ibarbo', liga: null, gruppen: ['fifa-kult'],
    vereine: [{ verein: 'cagliari', von: 2011, bis: 2015 }],
  },
};
const vereine = {
  bvb: { name: 'Borussia Dortmund', liga: 'BL1', stichwoerter: ['bvb', 'dortmund'] },
  bayern: { name: 'Bayern München', liga: 'BL1', stichwoerter: ['bayern'] },
  cagliari: { name: 'Cagliari Calcio', liga: 'SA', stichwoerter: ['cagliari'] },
};

function auktion(item_id, aenderungen = {}) {
  return {
    item_id, titel: 'Marco Reus Autogramm', bild: 'https://example.com/reus.jpg',
    url: `https://www.ebay.de/itm/${item_id}`, preis_cent: 1000, waehrung: 'EUR',
    gebote: 3, versand_cent: 250, start: '2026-11-01T12:00:00Z',
    ende: '2026-11-07T12:00:00Z', zuerst_gesehen: '2026-11-02T07:00:00Z',
    zuletzt_gesehen: '2026-11-06T07:00:00Z', spieler: ['marco-reus'],
    vereine: ['bvb'], typen: ['auto'], verdaechtig: false, status: 'laufend',
    endpreis_cent: null, ...aenderungen,
  };
}

function ids(auktionen, filter = {}) {
  return filtere(auktionen, { ...STANDARD, ...filter }, jetzt, spielerById, vereine)
    .map(auktion => auktion.item_id);
}

test('typ filtert', () => {
  const daten = [
    auktion('101'),
    auktion('102', { typen: ['relic'] }),
    auktion('103', { typen: ['rookie', 'auto'] }),
    auktion('104', { typen: [] }),
  ];
  assert.deepEqual(ids(daten, { typ: 'auto' }), ['101', '103']);
  assert.deepEqual(ids(daten, { typ: 'alle' }), ['101', '102', '103', '104']);
});

test('verein und liga', () => {
  const daten = [
    auktion('201', { spieler: ['marco-reus'], vereine: ['bvb'] }),
    auktion('202', { spieler: ['jamal-musiala'], vereine: [] }),
    auktion('203', { spieler: [], vereine: ['bayern'] }),
    auktion('204', { spieler: ['victor-ibarbo'], vereine: ['cagliari'] }),
    auktion('205', { spieler: ['marco-reus'], vereine: [] }),
    auktion('206', { spieler: [], vereine: [] }),
  ];
  assert.deepEqual(ids(daten, { verein: 'bvb' }), ['201']);
  assert.deepEqual(ids(daten, { liga: 'BL1' }), ['201', '202', '203']);
  assert.deepEqual(ids(daten, { verein: 'bvb', liga: 'BL1' }), ['201']);
  assert.deepEqual(ids(daten, { verein: 'bvb', liga: 'SA' }), []);
});

test('gruppe', () => {
  const daten = [
    auktion('301'),
    auktion('302', { spieler: ['victor-ibarbo'], vereine: ['cagliari'] }),
    auktion('303', { spieler: ['marco-reus', 'victor-ibarbo'] }),
    auktion('304', { spieler: [] }),
  ];
  assert.deepEqual(ids(daten, { gruppe: 'fifa-kult' }), ['302', '303']);
});

test('spieler', () => {
  const daten = [
    auktion('351'),
    auktion('352', { spieler: ['jamal-musiala'] }),
    auktion('353', { spieler: ['marco-reus', 'jamal-musiala'] }),
    auktion('354', { spieler: [] }),
  ];
  assert.deepEqual(ids(daten, { spieler: 'jamal-musiala' }), ['352', '353']);
});

test('max preis', () => {
  const daten = [
    auktion('401', { preis_cent: 999 }),
    auktion('402', { preis_cent: 1000, versand_cent: 400 }),
    auktion('403', { preis_cent: 1001 }),
  ];
  assert.deepEqual(ids(daten, { max_preis_cent: 1000 }), ['401', '402']);
  assert.deepEqual(ids(daten, { max_preis_cent: null }), ['401', '402', '403']);
});

test('ende in 24 h', () => {
  const daten = [
    auktion('501', { ende: '2026-11-07T11:00:00Z' }),
    auktion('502', { ende: '2026-11-07T18:00:00Z' }),
    auktion('503', { ende: '2026-11-06T11:59:59Z', status: 'beendet' }),
    auktion('504', { ende: '2026-11-13T13:00:00Z' }),
  ];
  assert.deepEqual(ids(daten, { ende_in_h: 24 }), ['501']);
  assert.deepEqual(ids(daten, { ende_in_h: 168 }), ['501', '502']);
});

test('ende_in_h null fürs Archiv', () => {
  const daten = [
    auktion('601', {
      start: '2026-09-01T12:00:00Z', ende: '2026-09-08T12:00:00Z',
      zuerst_gesehen: '2026-09-02T07:00:00Z', zuletzt_gesehen: '2026-09-08T07:00:00Z',
      status: 'beendet', endpreis_cent: null,
    }),
    auktion('602', { ende: '2026-11-06T11:00:00Z', status: 'beendet' }),
    auktion('603', { ende: '2026-11-20T12:00:00Z' }),
  ];
  assert.deepEqual(ids(daten, { ende_in_h: null }), ['601', '602', '603']);
});

test('verdächtige ausgeblendet', () => {
  const daten = [
    auktion('701'),
    auktion('702', { titel: 'Marco Reus facsimile auto', verdaechtig: true }),
  ];
  assert.deepEqual(ids(daten), ['701']);
  assert.deepEqual(ids(daten, { verdaechtige: true }), ['701', '702']);
});

test('nicht zugeordnet', () => {
  const daten = [
    auktion('801'),
    auktion('802', { spieler: [], vereine: ['bvb'] }),
    auktion('803', { spieler: [], vereine: [] }),
  ];
  assert.deepEqual(ids(daten, { nicht_zugeordnet: true }), ['802', '803']);
  assert.deepEqual(ids(daten, { nicht_zugeordnet: false }), ['801', '802', '803']);
});

test('sortiert nach ende', () => {
  const daten = [
    auktion('901', { ende: '2026-11-09T12:00:00Z' }),
    auktion('902', { ende: '2026-11-06T13:00:00Z' }),
    auktion('903', { ende: '2026-11-07T12:00:00Z' }),
  ];
  assert.deepEqual(ids(daten), ['902', '903', '901']);
});

test('findeSpieler: wie der Suchlauf über vollen Namen oder Suchnamen, akzent- und schreibweisenfrei', () => {
  const liste = [
    { id: 'erling-haaland', name: 'Erling Haaland', suchnamen: ['haaland'] },
    { id: 'victor-ibarbo', name: 'Víctor Ibarbo', suchnamen: ['ibarbo'] },
    { id: 'a', name: 'Anton Müller', suchnamen: ['muller'] },
    { id: 'b', name: 'Bernd Müller', suchnamen: ['muller'] },
  ];
  assert.equal(findeSpieler('Haaland', liste), 'erling-haaland');
  assert.equal(findeSpieler('  victor   IBARBO ', liste), 'victor-ibarbo');
  assert.equal(findeSpieler('Müller', liste), null); // mehrdeutig
  assert.equal(findeSpieler('Unbekannt', liste), null);
  assert.equal(findeSpieler('!!!', liste), null);
});

test('auflage: kleinste Nummerierung aus dem Titel, Saisonangaben zählen nicht', () => {
  assert.equal(auflage('Topps Reus Auto 12/25'), 25);
  assert.equal(auflage('Gold 1/1 Superfractor'), 1);
  assert.equal(auflage('Topps 2023/24 Chrome /99'), 99);
  assert.equal(auflage('Topps Chrome 23/24 Base'), null);
  assert.equal(auflage('Panini 2023/2024'), null);
  assert.equal(auflage('Reus Base'), null);
});

test('neue Filter: Deutschland, Titelsuche, Auflage, Gebote, Preis mit Versand', () => {
  const liste = [
    auktion('de', { land: 'DE', titel: 'Topps Merlin Reus Auto /25', gebote: 0, preis_cent: 900, versand_cent: 200 }),
    auktion('uk', { land: 'GB', titel: 'Topps Chrome Reus Auto /99', gebote: 2, preis_cent: 500, versand_cent: 900 }),
    auktion('alt', { titel: 'Panini Prizm Réus Gold 1/1', gebote: 5, preis_cent: 3000, versand_cent: 0 }),
  ];
  assert.deepEqual(ids(liste, { nur_de: true }), ['de']);
  assert.deepEqual(ids(liste, { text: 'merlin' }), ['de']);
  assert.deepEqual(ids(liste, { text: 'reus  GOLD' }), ['alt']);
  assert.deepEqual(ids(liste, { max_auflage: 25 }).sort(), ['alt', 'de']);
  assert.deepEqual(ids(liste, { gebote: 'ohne' }), ['de']);
  assert.deepEqual(ids(liste, { gebote: 'mit' }).sort(), ['alt', 'uk']);
  assert.deepEqual(ids(liste, { max_preis_cent: 1000 }).sort(), ['de', 'uk']);
  assert.deepEqual(ids(liste, { max_preis_cent: 1000, preis_mit_versand: true }), []);
  assert.deepEqual(ids(liste, { max_preis_cent: 1100, preis_mit_versand: true }), ['de']);
});

test('Sortierung und nur neue seit dem letzten gesehenen Lauf', () => {
  const liste = [
    auktion('a', { ende: '2026-11-06T13:00:00Z', preis_cent: 900, zuerst_gesehen: '2026-11-05T06:00:00Z' }),
    auktion('b', { ende: '2026-11-06T14:00:00Z', preis_cent: 100, versand_cent: 2000, zuerst_gesehen: '2026-11-06T06:00:00Z' }),
    auktion('c', { ende: '2026-11-06T15:00:00Z', preis_cent: 500, zuerst_gesehen: '2026-11-06T18:00:00Z' }),
  ];
  assert.deepEqual(ids(liste), ['a', 'b', 'c']);
  assert.deepEqual(ids(liste, { sortierung: 'preis' }), ['b', 'c', 'a']);
  assert.deepEqual(ids(liste, { sortierung: 'preis', preis_mit_versand: true }), ['c', 'a', 'b']);
  assert.deepEqual(ids(liste, { sortierung: 'neu' }), ['c', 'b', 'a']);
  const mitStichtag = (f) => filtere(liste, { ...STANDARD, ...f }, jetzt, spielerById, vereine, '2026-11-05T06:00:00Z').map(a => a.item_id);
  assert.deepEqual(mitStichtag({ nur_neue: true }), ['b', 'c']);
  assert.deepEqual(ids(liste, { nur_neue: true }), ['a', 'b', 'c']); // ohne Stichtag (erster Besuch) kein Filter
});
