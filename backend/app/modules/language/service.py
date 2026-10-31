"""Language layer. The MockLanguageService is a deterministic stand-in for a future Sarvam AI
adapter (speech/translation). It does NOT call any external service."""
from __future__ import annotations

from typing import Protocol

from app.core.errors import NotAvailableError
from app.modules.language.templates import T
from app.schemas.domain import Language

_HINGLISH = {
    "mera", "meri", "kal", "nahi", "nahin", "kyu", "kyun", "aaya", "paisa", "abhi", "tak",
    "kab", "kya", "hai", "kaise", "mujhe", "karo", "kijiye", "account",
}


class LanguageService(Protocol):
    def detect(self, text: str) -> Language: ...
    def render(self, key: str, language: Language, **values: object) -> str: ...


class MockLanguageService:
    def detect(self, text: str) -> Language:
        for ch in text:
            cp = ord(ch)
            if 0x0900 <= cp <= 0x097F:
                return Language.HI
            if 0x0C00 <= cp <= 0x0C7F:
                return Language.TE
            if 0x0C80 <= cp <= 0x0CFF:
                return Language.KN
        words = {w.strip(".,?!").lower() for w in text.split()}
        # "account" alone is English too, so require 2+ distinctive Hinglish words.
        return Language.HI if len(words & (_HINGLISH - {"account"})) >= 2 else Language.EN

    def render(self, key: str, language: Language, **values: object) -> str:
        variants = T[key]
        template = variants.get(language) or variants[Language.EN]
        return template.format(**values)


class SarvamLanguageService:
    """Placeholder: Sarvam AI integration is PLANNED, not implemented."""

    def __init__(self) -> None:
        raise NotAvailableError("Sarvam AI language layer is not integrated in this prototype.")
