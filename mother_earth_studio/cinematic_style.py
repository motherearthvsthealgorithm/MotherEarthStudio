from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CinematicCaptionStyle:
    """Locked baseline for calm, reflective caption emphasis."""

    max_words: int = 5
    font_color: str = "0xF4F0E8"
    font_size_divisor: int = 25
    border_width: int = 1


DEFAULT_CINEMATIC_STYLE = CinematicCaptionStyle()


def split_into_reflective_phrases(
    text: str,
    max_words: int = DEFAULT_CINEMATIC_STYLE.max_words,
) -> list[str]:
    """Split text into short thought units without rewriting the wording."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []

    clauses = [
        part.strip()
        for part in re.split(r"(?<=[,;:!?—.])\s+", clean)
        if part.strip()
    ]

    phrases: list[str] = []
    for clause in clauses:
        words = clause.split()
        while words:
            take = min(max_words, len(words))
            if len(words) > max_words:
                window = words[:max_words]
                conjunctions = {
                    "and", "but", "because", "so", "while",
                    "when", "that", "which", "or",
                }
                breaks = [
                    index
                    for index, word in enumerate(window[1:], start=1)
                    if re.sub(r"[^\w']", "", word.lower()) in conjunctions
                ]
                if breaks and breaks[-1] >= 2:
                    take = breaks[-1]

            phrase = " ".join(words[:take]).strip()
            if phrase:
                phrases.append(phrase)
            words = words[take:]

    return phrases
