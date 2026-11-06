"""JSON-Dateien in UTF-8 lesen und atomar schreiben."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


def lese_json(pfad: Path, standard):
    """Bei fehlender Datei den Standard zurueckgeben."""
    try:
        with Path(pfad).open(encoding="utf-8") as datei:
            return json.load(datei)
    except FileNotFoundError:
        return standard


def schreibe_json(pfad: Path, daten) -> None:
    """Eine vollstaendig geschriebene Datei atomar einsetzen."""
    with _atomare_datei(pfad) as datei:
        json.dump(daten, datei, ensure_ascii=False, indent=1)
        datei.write("\n")


def schreibe_auktionen(pfad: Path, auktionen: list[dict]) -> None:
    """Auktionen kompakt mit je einer JSON-Zeile atomar schreiben."""
    with _atomare_datei(pfad) as datei:
        datei.write('{"auktionen": [\n')
        for nummer, auktion in enumerate(auktionen):
            if nummer:
                datei.write(",\n")
            datei.write(json.dumps(auktion, ensure_ascii=False, separators=(",", ":")))
        datei.write("\n]}\n")


@contextmanager
def _atomare_datei(pfad: Path):
    """Im Zielverzeichnis schreiben und erst nach flush/fsync ersetzen."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    temporaer = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=pfad.parent,
            prefix=f".{pfad.name}.", suffix=".tmp", delete=False,
        ) as datei:
            temporaer = Path(datei.name)
            yield datei
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(temporaer, pfad)
    finally:
        if temporaer is not None:
            temporaer.unlink(missing_ok=True)
