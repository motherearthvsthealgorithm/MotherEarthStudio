from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .adaptive_typography import layout_overlay_text


@dataclass(frozen=True)
class StoryCaptionStyle:
    max_words: int = 9
    max_characters: int = 46
    max_line_characters: int = 24
    min_duration: float = 1.35
    max_duration: float = 4.8
    merge_gap: float = 0.22
    inter_caption_gap: float = 0.10
    fade_duration: float = 0.18
    font_color: str = "0xF4F0E8"
    base_font_size_divisor: int = 27
    small_font_size_divisor: int = 30
    y_position: float = 0.735


DEFAULT_STORY_CAPTION_STYLE = StoryCaptionStyle()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\n", " ")).strip()


def _ends_thought(text: str) -> bool:
    return bool(re.search(r"[.!?…][\"')\]]?$", text.strip()))


def _starts_new_thought(text: str) -> bool:
    first = normalize_text(text).split(" ", 1)[0].lower().strip("\"'([{“‘")
    return first in {
        "but", "however", "instead", "still", "yet", "because",
        "so", "then", "now", "sometimes", "maybe", "perhaps",
    }


def merge_into_thought_units(
    cues: list[tuple[float, float, str]],
    style: StoryCaptionStyle = DEFAULT_STORY_CAPTION_STYLE,
) -> list[tuple[float, float, str]]:
    """Merge adjacent subtitle fragments into readable editorial thoughts."""
    result: list[tuple[float, float, str]] = []
    current_start: float | None = None
    current_end = 0.0
    current_text = ""

    def flush() -> None:
        nonlocal current_start, current_end, current_text
        text = normalize_text(current_text)
        if current_start is not None and text:
            result.append((current_start, current_end, text))
        current_start = None
        current_end = 0.0
        current_text = ""

    for start, end, raw_text in cues:
        text = normalize_text(raw_text)
        if not text or end <= start:
            continue

        if current_start is None:
            current_start, current_end, current_text = start, end, text
            continue

        candidate = normalize_text(f"{current_text} {text}")
        candidate_words = len(candidate.split())
        candidate_duration = end - current_start
        gap = max(0.0, start - current_end)

        should_break = (
            _ends_thought(current_text)
            or _starts_new_thought(text)
            or gap > style.merge_gap
            or candidate_words > style.max_words
            or len(candidate) > style.max_characters
            or candidate_duration > style.max_duration
        )

        if should_break:
            flush()
            current_start, current_end, current_text = start, end, text
        else:
            current_end = end
            current_text = candidate

    flush()
    return result


def _line_visual_weight(text: str) -> float:
    """Approximate proportional-font width without requiring a font library."""
    narrow = set(" ilI1.,:;!'|`")
    wide = set("MW@%&QO")
    weight = 0.0
    for char in text:
        if char in narrow:
            weight += 0.48
        elif char in wide:
            weight += 1.28
        elif char.isupper():
            weight += 1.05
        else:
            weight += 0.9
    return weight


def balance_two_lines(
    text: str,
    style: StoryCaptionStyle = DEFAULT_STORY_CAPTION_STYLE,
) -> str:
    """Create one or two visually balanced lines that stay inside the safe width."""
    clean = normalize_text(text)
    words = clean.split()
    if not words:
        return ""

    if len(clean) <= style.max_line_characters and _line_visual_weight(clean) <= 22.5:
        return clean

    best: tuple[float, str, str] | None = None
    for split in range(1, len(words)):
        first = " ".join(words[:split])
        second = " ".join(words[split:])
        w1 = _line_visual_weight(first)
        w2 = _line_visual_weight(second)
        overflow = max(0.0, w1 - 23.0) + max(0.0, w2 - 23.0)
        orphan_penalty = 4.0 if len(words[split:]) == 1 else 0.0
        punctuation_bonus = -0.8 if re.search(r"[,;:—]$", first) else 0.0
        score = abs(w1 - w2) + overflow * 8.0 + orphan_penalty + punctuation_bonus
        if best is None or score < best[0]:
            best = (score, first, second)

    if best is None:
        return clean
    return f"{best[1]}\n{best[2]}"


def choose_font_divisor(
    balanced_text: str,
    style: StoryCaptionStyle = DEFAULT_STORY_CAPTION_STYLE,
) -> int:
    longest = max((_line_visual_weight(line) for line in balanced_text.splitlines()), default=0.0)
    return style.small_font_size_divisor if longest > 21.0 else style.base_font_size_divisor


def prepare_story_overlays(
    cues: list[tuple[float, float, str]],
    time_offset: float = 0.0,
    style: StoryCaptionStyle = DEFAULT_STORY_CAPTION_STYLE,
) -> list[dict]:
    units = merge_into_thought_units(cues, style)
    overlays: list[dict] = []
    previous_end = 0.0

    for start, end, text in units:
        start += time_offset
        end += time_offset
        start = max(start, previous_end + style.inter_caption_gap if overlays else start)
        end = max(end, start + style.min_duration)
        end = min(end, start + style.max_duration)
        layout = layout_overlay_text(text)
        overlays.append({
            "start": start,
            "end": end,
            "text": layout.text,
            "font_divisor": layout.font_divisor,
            "fit_status": layout.fit_status,
            "fit_reason": layout.fit_reason,
        })
        previous_end = end

    return overlays


def write_overlay_text_files(overlays: list[dict], temp_dir: Path) -> list[Path]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, overlay in enumerate(overlays, start=1):
        path = temp_dir / f"story_caption_{index:04d}.txt"
        path.write_text(str(overlay["text"]), encoding="utf-8")
        paths.append(path)
    return paths
