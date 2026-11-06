import test from 'node:test';
import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { GitHub, KonfliktFehler, repoAusAdresse } from './github.js';

const basis = 'https://api.github.com/repos/Dabvud/auktionsfinder';
const pfad = 'daten/suchen.json';
const token = 'github_pat_test_123';

function antwort(status, daten) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() { return structuredClone(daten); },
    async text() { return daten === null ? '' : JSON.stringify(daten); },
  };
}

function fakeFetch(schritte) {
  const aufrufe = [];
  return {
    aufrufe,
    async fetch(url, init) {
      const schritt = schritte[aufrufe.length];
      aufrufe.push({ url, init });
      assert.ok(schritt, `Unerwarteter Abruf: ${url}`);
      assert.equal(url, schritt.url);
      assert.equal(init?.method ?? 'GET', schritt.methode ?? 'GET');
      if (schritt.accept) {
        assert.equal(new Headers(init?.headers).get('Accept'), schritt.accept);
      }
      return antwort(schritt.status ?? 200, schritt.daten);
    },
  };
}

function client(fetch) {
  return new GitHub({ owner: 'Dabvud', repo: 'auktionsfinder', token, fetch });
}

function pruefeApiHeader(aufrufe) {
  for (const { init } of aufrufe) {
    const headers = new Headers(init?.headers);
    assert.equal(headers.get('Authorization'), `Bearer ${token}`);
    assert.equal(headers.get('X-GitHub-Api-Version'), '2022-11-28');
  }
}

function leseSchritte(daten, sha) {
  return [
    { url: `${basis}/contents/${pfad}`, accept: 'application/vnd.github.raw+json', daten },
    { url: `${basis}/contents/${pfad}`, accept: 'application/vnd.github+json', daten: { sha } },
  ];
}

function putSchritt(status, sha) {
  return {
    url: `${basis}/contents/${pfad}`, methode: 'PUT', status,
    daten: status === 409 ? { message: 'sha does not match' } : { content: { sha } },
  };
}

function putDaten(aufruf) {
  const body = JSON.parse(aufruf.init.body);
  return JSON.parse(Buffer.from(body.content, 'base64').toString('utf8'));
}

test('leseJson mit Token', async () => {
  const daten = [{ id: 'bvb-autos', name: 'BVB Autos', filter: { typ: 'auto', verein: 'bvb' } }];
  const fake = fakeFetch(leseSchritte(daten, 'sha-suchen-1'));

  assert.deepEqual(await client(fake.fetch).leseJson(pfad), { daten, sha: 'sha-suchen-1' });
  assert.equal(fake.aufrufe.length, 2);
  pruefeApiHeader(fake.aufrufe);
});

test('leseJson ohne Token', async () => {
  const daten = [{ id: 'ibarbo', name: 'Ibarbo', filter: { spieler: 'victor-ibarbo' } }];
  const fake = fakeFetch([{ url: pfad, daten }]);
  const github = new GitHub({ owner: 'Dabvud', repo: 'auktionsfinder', token: null, fetch: fake.fetch });

  assert.deepEqual(await github.leseJson(pfad), { daten, sha: null });
  assert.equal(fake.aufrufe.length, 1);
  assert.equal(new Headers(fake.aufrufe[0].init?.headers).get('Authorization'), null);
});

test('schreibeJson base64 utf-8', async () => {
  const daten = [{ id: 'ueberflieger', name: 'Überflieger ⚽', filter: { typ: 'rookie' } }];
  const fake = fakeFetch([putSchritt(200, 'sha-suchen-neu')]);

  const sha = await client(fake.fetch).schreibeJson(pfad, daten, 'sha-suchen-alt', 'Suche Überflieger speichern');

  assert.equal(sha, 'sha-suchen-neu');
  assert.equal(fake.aufrufe.length, 1);
  const body = JSON.parse(fake.aufrufe[0].init.body);
  const json = JSON.stringify(daten, null, 1);
  assert.deepEqual(body, {
    message: 'Suche Überflieger speichern',
    content: Buffer.from(json, 'utf8').toString('base64'),
    sha: 'sha-suchen-alt',
  });
  assert.equal(Buffer.from(body.content, 'base64').toString('utf8'), json);
  pruefeApiHeader(fake.aufrufe);
});

test('schreibeJson wirft KonfliktFehler bei 409', async () => {
  const fake = fakeFetch([putSchritt(409)]);

  await assert.rejects(
    () => client(fake.fetch).schreibeJson(pfad, [], 'sha-veraltet', 'Suche speichern'),
    KonfliktFehler,
  );
  assert.equal(fake.aufrufe.length, 1);
  pruefeApiHeader(fake.aufrufe);
});

test('aendereJson bei 409', async () => {
  const vorhandene = { id: 'bvb-autos', name: 'BVB Autos', filter: { typ: 'auto', verein: 'bvb' } };
  const fremde = { id: 'relics', name: 'Fremde Suche', filter: { typ: 'relic' } };
  const eigene = { id: 'rookies', name: 'Meine Suche', filter: { typ: 'rookie' } };
  const fake = fakeFetch([
    ...leseSchritte([vorhandene], 'sha-1'), putSchritt(409),
    ...leseSchritte([vorhandene, fremde], 'sha-2'), putSchritt(200, 'sha-3'),
  ]);
  const geleseneDaten = [];

  await client(fake.fetch).aendereJson(pfad, daten => {
    geleseneDaten.push(structuredClone(daten));
    return [...daten, eigene];
  }, 'Meine Suche speichern');

  assert.deepEqual(geleseneDaten, [[vorhandene], [vorhandene, fremde]]);
  assert.equal(fake.aufrufe.length, 6);
  assert.deepEqual(putDaten(fake.aufrufe[2]), [vorhandene, eigene]);
  assert.deepEqual(putDaten(fake.aufrufe[5]), [vorhandene, fremde, eigene]);
  assert.equal(JSON.parse(fake.aufrufe[2].init.body).sha, 'sha-1');
  assert.equal(JSON.parse(fake.aufrufe[5].init.body).sha, 'sha-2');
  for (const index of [2, 5]) {
    assert.equal(JSON.parse(fake.aufrufe[index].init.body).message, 'Meine Suche speichern');
  }
  pruefeApiHeader(fake.aufrufe);
});

test('aendereJson wiederholt bei 409 genau einmal', async () => {
  const fake = fakeFetch([
    ...leseSchritte([], 'sha-1'), putSchritt(409),
    ...leseSchritte([{ id: 'fremd' }], 'sha-2'), putSchritt(409),
  ]);
  let aenderungen = 0;

  await assert.rejects(() => client(fake.fetch).aendereJson(pfad, daten => {
    aenderungen += 1;
    return [...daten, { id: 'eigen' }];
  }, 'Suche speichern'), KonfliktFehler);

  assert.equal(aenderungen, 2);
  assert.equal(fake.aufrufe.length, 6);
  assert.deepEqual(putDaten(fake.aufrufe[5]), [{ id: 'fremd' }, { id: 'eigen' }]);
  pruefeApiHeader(fake.aufrufe);
});

test('dispatch', async () => {
  const fake = fakeFetch([{
    url: `${basis}/actions/workflows/suchlauf.yml/dispatches`,
    methode: 'POST', status: 204, daten: null,
  }]);

  await client(fake.fetch).starteSuchlauf();

  assert.equal(fake.aufrufe.length, 1);
  assert.deepEqual(JSON.parse(fake.aufrufe[0].init.body), { ref: 'main' });
  pruefeApiHeader(fake.aufrufe);
});

test('letzterLauf', async () => {
  const fake = fakeFetch([{
    url: `${basis}/actions/workflows/suchlauf.yml/runs?per_page=1`,
    daten: { workflow_runs: [
      { status: 'completed', conclusion: 'success', created_at: '2026-11-06T06:00:00Z' },
      { status: 'completed', conclusion: 'failure', created_at: '2026-11-05T18:00:00Z' },
    ] },
  }]);

  assert.deepEqual(await client(fake.fetch).letzterLauf(), {
    status: 'completed', conclusion: 'success', erstellt: '2026-11-06T06:00:00Z',
  });
  assert.equal(fake.aufrufe.length, 1);
  pruefeApiHeader(fake.aufrufe);
});

test('Standard-fetch wird ohne fremdes this aufgerufen (Browser: Illegal invocation)', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = function (url) {
    if (this !== undefined && this !== globalThis) throw new TypeError("Failed to execute 'fetch' on 'Window': Illegal invocation");
    return Promise.resolve({ status: 200, ok: true, text: async () => '{"x":1}', json: async () => ({ x: 1 }) });
  };
  try {
    const ergebnis = await new GitHub({ owner: 'Dabvud', repo: 'auktionsfinder' }).leseJson('daten/status.json');
    assert.deepEqual(ergebnis, { daten: { x: 1 }, sha: null });
  } finally {
    globalThis.fetch = original;
  }
});

test('repoAusAdresse: jede Kopie spricht ihr eigenes Repo an', () => {
  assert.deepEqual(repoAusAdresse('dabvud.github.io', '/auktionsfinder/'), { owner: 'dabvud', repo: 'auktionsfinder' });
  assert.deepEqual(repoAusAdresse('freund.github.io', '/meine-karten/index.html'), { owner: 'freund', repo: 'meine-karten' });
  assert.deepEqual(repoAusAdresse('freund.github.io', '/'), { owner: 'freund', repo: 'freund.github.io' });
  assert.equal(repoAusAdresse('127.0.0.1', '/index.html'), null);
});
