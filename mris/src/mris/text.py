"""Text normalisation helpers shared by matching, parsing and evidence analysis."""

from __future__ import annotations

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    """Remove diacritics/tatweel and unify common letter variants."""
    text = _ARABIC_DIACRITICS.sub("", text)
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return text


def normalize_text(text: str) -> str:
    """Lowercase, Arabic-normalised, punctuation-free, single-spaced text."""
    text = unicodedata.normalize("NFKC", text or "")
    text = normalize_arabic(text).lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def normalize_title(title: str) -> str:
    """Canonical key for movie titles ("The Town" == "the town", "Carry-On" == "carry on")."""
    norm = normalize_text(title)
    norm = re.sub(r"\b(19|20)\d{2}\b$", "", norm).strip()  # trailing year in the title string
    return norm


def split_sentences(text: str) -> list[str]:
    text = _SPACES.sub(" ", text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?؟])\s+|\s*[\n•]\s*", text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def truncate(text: str, limit: int = 280) -> str:
    text = _SPACES.sub(" ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
