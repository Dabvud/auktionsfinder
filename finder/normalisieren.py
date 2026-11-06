"""Namen und Titel auf vergleichbare Wortfolgen reduzieren."""

import re
import unicodedata


def vereinheitliche(text: str) -> str:
    """Kleinschreibung, Akzente und Satzzeichen vereinheitlichen."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(zeichen for zeichen in text if not unicodedata.combining(zeichen))
    return " ".join(re.sub(r"[^a-z0-9]", " ", text).split())
