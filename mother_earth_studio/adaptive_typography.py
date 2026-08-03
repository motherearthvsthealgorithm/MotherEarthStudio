from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TypographyLayout:
    text: str
    font_divisor: int
    fit_status: str
    fit_reason: str
    longest_line_weight: float

    @property
    def fits(self) -> bool:
        return self.fit_status != "overflow"


def visual_weight(text: str) -> float:
    """Approximate Helvetica Neue width in font-size units."""
    narrow = set(" ilI1.,:;!'|`[]()")
    wide = set("MW@%&QO#")
    total = 0.0
    for char in text:
        if char in narrow:
            total += 0.46
        elif char in wide:
            total += 1.28
        elif char.isupper():
            total += 1.04
        else:
            total += 0.88
    return total


def _candidate_breaks(words: list[str], max_lines: int) -> list[list[str]]:
    if max_lines <= 1 or len(words) <= 1:
        return [[" ".join(words)]]
    candidates: list[list[str]] = []
    if max_lines == 2:
        for first in range(1, len(words)):
            candidates.append([" ".join(words[:first]), " ".join(words[first:])])
        return candidates
    for first in range(1, len(words) - 1):
        for second in range(first + 1, len(words)):
            candidates.append([
                " ".join(words[:first]),
                " ".join(words[first:second]),
                " ".join(words[second:]),
            ])
    return candidates


def _score_lines(lines: list[str], capacity: float) -> float:
    weights = [visual_weight(line) for line in lines]
    overflow = sum(max(0.0, weight - capacity) for weight in weights)
    imbalance = max(weights) - min(weights) if weights else 0.0
    orphan = 5.0 if len(lines[-1].split()) == 1 else 0.0
    punctuation = sum(-0.55 for line in lines[:-1] if re.search(r"[,;:—]$", line))
    return overflow * 50.0 + imbalance + orphan + punctuation


def layout_overlay_text(
    text: str,
    *,
    frame_width: int = 1080,
    frame_height: int = 1920,
    safe_width_ratio: float = 0.80,
    preferred_divisor: int = 27,
    minimum_divisor: int = 33,
    max_lines: int = 2,
) -> TypographyLayout:
    """
    Balance lines and scale type until it fits the title-safe width.

    Divisors increase as the font gets smaller. We preserve two lines as the
    visual ideal and report overflow rather than silently creating dense text.
    """
    clean = re.sub(r"\s+", " ", str(text)).strip()
    if not clean:
        return TypographyLayout("", preferred_divisor, "overflow", "empty overlay", 0.0)

    words = clean.split()
    best_layout: TypographyLayout | None = None
    for divisor in range(preferred_divisor, minimum_divisor + 1):
        font_size = frame_height / divisor
        # Empirical scale for Helvetica Neue bold, leaving 20% horizontal safety.
        capacity = (frame_width * safe_width_ratio) / max(1.0, font_size * 0.56)
        candidates = [[clean]] + _candidate_breaks(words, max_lines)
        # Long documentary thoughts may use a restrained third line before
        # the engine declares overflow. This is preferable to clipping.
        if max_lines == 2 and len(words) >= 10:
            candidates += _candidate_breaks(words, 3)
        lines = min(candidates, key=lambda item: _score_lines(item, capacity))
        longest = max((visual_weight(line) for line in lines), default=0.0)
        if longest <= capacity:
            usage = longest / capacity if capacity else 1.0
            status = "good" if usage <= 0.88 and len(lines) <= 2 else "tight"
            reason = (
                f"fits at {round(font_size)}px with {len(lines)} line(s)"
                if status == "good"
                else f"fits at {round(font_size)}px with {len(lines)} line(s); consider splitting for more breathing room"
            )
            return TypographyLayout("\n".join(lines), divisor, status, reason, longest)
        candidate = TypographyLayout(
            "\n".join(lines), divisor, "overflow",
            "does not fit the 80% title-safe width; split or shorten this highlight",
            longest,
        )
        best_layout = candidate

    assert best_layout is not None
    return best_layout
