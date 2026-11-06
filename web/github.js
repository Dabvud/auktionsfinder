/** Meldet einen Schreibkonflikt mit einer inzwischen geänderten Datei. */
export class KonfliktFehler extends Error {
  constructor() {
    super('Die Datei wurde inzwischen geändert.');
    this.name = 'KonfliktFehler';
  }
}

/** Liest und schreibt JSON-Dateien und steuert den GitHub-Suchlauf. */
export class GitHub {
  #basis;
  #schluessel;
  #abrufen;

  constructor({ owner: eigentuemer, repo: repository, token: schluessel, fetch: abrufen = globalThis.fetch }) {
    this.#basis = `https://api.github.com/repos/${encodeURIComponent(eigentuemer)}/${encodeURIComponent(repository)}`;
    this.#schluessel = schluessel;
    this.#abrufen = abrufen;
  }

  async #anfrage(url, optionen) {
    const antwort = await this.#abrufen(url, optionen);
    if (antwort.status === 409 && optionen?.method === 'PUT') {
      throw new KonfliktFehler();
    }
    if (!antwort.ok) {
      throw new Error(`GitHub-Anfrage fehlgeschlagen (HTTP ${antwort.status}).`);
    }
    return antwort;
  }

  async #apiAnfrage(pfad, { methode = 'GET', akzeptiert = 'application/vnd.github+json', daten } = {}) {
    if (!this.#schluessel) throw new Error('GitHub-Schlüssel fehlt.');

    const kopfzeilen = {
      Accept: akzeptiert,
      Authorization: `Bearer ${this.#schluessel}`,
      'X-GitHub-Api-Version': '2022-11-28',
    };
    const optionen = { method: methode, headers: kopfzeilen };
    if (daten !== undefined) {
      kopfzeilen['Content-Type'] = 'application/json';
      optionen.body = JSON.stringify(daten);
    }
    return this.#anfrage(`${this.#basis}/${pfad}`, optionen);
  }

  #dateipfad(pfad) {
    return `contents/${pfad.split('/').map(encodeURIComponent).join('/')}`;
  }

  async leseJson(pfad) {
    if (!this.#schluessel) {
      const antwort = await this.#anfrage(pfad);
      return { daten: JSON.parse(await antwort.text()), sha: null };
    }

    const dateipfad = this.#dateipfad(pfad);
    const inhalt = await this.#apiAnfrage(dateipfad, {
      akzeptiert: 'application/vnd.github.raw+json',
    });
    const daten = JSON.parse(await inhalt.text());
    const antwort = await this.#apiAnfrage(dateipfad);
    const metadaten = await antwort.json();
    return { daten, sha: metadaten.sha };
  }

  async schreibeJson(pfad, daten, sha, nachricht) {
    const bytes = new TextEncoder().encode(JSON.stringify(daten, null, 1));
    let binaertext = '';
    for (const byte of bytes) binaertext += String.fromCharCode(byte);

    const antwort = await this.#apiAnfrage(this.#dateipfad(pfad), {
      methode: 'PUT',
      daten: { message: nachricht, content: btoa(binaertext), sha },
    });
    const ergebnis = await antwort.json();
    return ergebnis.content.sha;
  }

  async aendereJson(pfad, aenderung, nachricht) {
    const { daten, sha } = await this.leseJson(pfad);
    const geaendert = aenderung(daten);
    try {
      return await this.schreibeJson(pfad, geaendert, sha, nachricht);
    } catch (fehler) {
      if (!(fehler instanceof KonfliktFehler)) throw fehler;
    }

    const neu = await this.leseJson(pfad);
    return this.schreibeJson(pfad, aenderung(neu.daten), neu.sha, nachricht);
  }

  async starteSuchlauf() {
    await this.#apiAnfrage('actions/workflows/suchlauf.yml/dispatches', {
      methode: 'POST',
      daten: { ref: 'main' },
    });
  }

  async letzterLauf() {
    const antwort = await this.#apiAnfrage('actions/workflows/suchlauf.yml/runs?per_page=1');
    const daten = await antwort.json();
    const lauf = daten.workflow_runs[0];
    if (!lauf) return null;
    return { status: lauf.status, conclusion: lauf.conclusion, erstellt: lauf.created_at };
  }
}
