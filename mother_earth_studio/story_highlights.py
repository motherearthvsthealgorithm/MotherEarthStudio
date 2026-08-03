from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .adaptive_typography import layout_overlay_text
from .story_first_caption_engine import (
    DEFAULT_STORY_CAPTION_STYLE,
    merge_into_thought_units,
)

HIGHLIGHTS_VERSION = 2


@dataclass
class StoryHighlight:
    text: str
    start: float
    end: float
    position: str = "lower_center"
    fade_duration: float = 0.28
    enabled: bool = True
    confidence: float = 1.0
    review_reason: str = ""

    def normalized(self) -> "StoryHighlight":
        text = re.sub(r"\s+", " ", self.text).strip()
        start = max(0.0, float(self.start))
        end = max(start + 0.8, float(self.end))
        position = self.position if self.position in {
            "upper_center", "middle_center", "lower_center"
        } else "lower_center"
        fade = min(0.75, max(0.0, float(self.fade_duration)))
        confidence = min(1.0, max(0.0, float(self.confidence)))
        return StoryHighlight(
            text, start, end, position, fade, bool(self.enabled),
            confidence, str(self.review_reason or "").strip(),
        )


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    def seconds(value: str) -> float:
        hours, minutes, rest = value.strip().split(":")
        secs, millis = rest.replace(".", ",").split(",")
        return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000

    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip())
    cues: list[tuple[float, float, str]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        left, right = [part.strip() for part in lines[timing_index].split("-->", 1)]
        text = " ".join(lines[timing_index + 1:]).strip()
        if text:
            cues.append((seconds(left), seconds(right), text))
    return cues


def _score(text: str, start: float, end: float) -> float:
    clean = re.sub(r"\s+", " ", text).strip()
    words = clean.split()
    score = min(len(words), 12) * 0.35
    if clean.endswith("?"):
        score += 3.5
    if re.search(r"\b(remember|forget|world|earth|nature|truth|future|because|means|change|question|wonder|belong|alive|loss|protect)\b", clean, re.I):
        score += 2.2
    if re.search(r"[.!?…]$", clean):
        score += 1.0
    duration = end - start
    if 2.2 <= duration <= 6.5:
        score += 1.0
    if len(clean) > 72:
        score -= 2.0
    return score


def assess_highlight_confidence(text: str, start: float, end: float) -> tuple[float, str]:
    clean = re.sub(r"\s+", " ", text).strip()
    words = clean.split()
    score = 0.92
    reasons: list[str] = []

    if not clean:
        return 0.0, "Empty overlay"
    if clean[0].islower():
        score -= 0.28
        reasons.append("starts mid-sentence")
    if len(words) <= 3:
        score -= 0.30
        reasons.append("very short fragment")
    if clean.lower().startswith(("and ", "but ", "because ", "so ", "it ", "they ", "this ")):
        score -= 0.18
        reasons.append("depends on earlier context")
    if not re.search(r"[.!?…]$", clean):
        score -= 0.10
        reasons.append("no clear ending")
    if clean.endswith(("from?", "to?", "of?", "with?")):
        score -= 0.25
        reasons.append("question appears incomplete")
    if end - start < 1.6:
        score -= 0.12
        reasons.append("brief screen time")
    if len(clean) > 82:
        score -= 0.12
        reasons.append("long overlay")

    return max(0.05, min(0.99, score)), ", ".join(reasons)


def quick_rewrite_text(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return clean
    clean = clean[0].upper() + clean[1:]
    if not re.search(r"[.!?…]$", clean):
        clean += "."
    return clean


def suggest_highlights_from_srt(path: Path, maximum: int = 10) -> list[StoryHighlight]:
    cues = parse_srt(path)
    units = merge_into_thought_units(cues, DEFAULT_STORY_CAPTION_STYLE)
    if not units:
        return []

    ranked = sorted(
        ((_score(text, start, end), start, end, text) for start, end, text in units),
        key=lambda item: (-item[0], item[1]),
    )
    selected: list[tuple[float, float, str]] = []
    for _score_value, start, end, text in ranked:
        midpoint = (start + end) / 2
        if any(abs(midpoint - ((s + e) / 2)) < 4.5 for s, e, _ in selected):
            continue
        selected.append((start, end, text))
        if len(selected) >= maximum:
            break

    selected.sort(key=lambda item: item[0])
    results: list[StoryHighlight] = []
    previous_end = -99.0
    for start, end, text in selected:
        start = max(start, previous_end + 0.75)
        end = min(max(end, start + 2.4), start + 6.0)
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean.split()) > 14:
            words = clean.split()
            clean = " ".join(words[:14]).rstrip(",;:") + ("…" if len(words) > 14 else "")
        confidence, reason = assess_highlight_confidence(clean, start, end)
        results.append(StoryHighlight(
            clean, start, end,
            confidence=confidence,
            review_reason=reason,
        ))
        previous_end = end
    return results


def save_highlights(path: Path, highlights: list[StoryHighlight], source: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [item.normalized() for item in highlights if item.text.strip()]
    data = {
        "version": HIGHLIGHTS_VERSION,
        "type": "mother-earth-story-highlights",
        "source": source,
        "highlights": [asdict(item) for item in normalized],
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def load_highlights(path: Path) -> list[StoryHighlight]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "mother-earth-story-highlights":
        raise ValueError("This JSON file is not a Mother Earth Studio story highlights file.")
    results = []
    for item in data.get("highlights", []):
        highlight = StoryHighlight(
            text=str(item.get("text", "")),
            start=float(item.get("start", 0.0)),
            end=float(item.get("end", 0.0)),
            position=str(item.get("position", "lower_center")),
            fade_duration=float(item.get("fade_duration", 0.28)),
            enabled=bool(item.get("enabled", True)),
            confidence=float(item.get("confidence", 1.0)),
            review_reason=str(item.get("review_reason", "")),
        ).normalized()
        if highlight.text and highlight.enabled:
            results.append(highlight)
    return sorted(results, key=lambda item: item.start)


def render_ready_overlays(path: Path, time_offset: float = 0.0) -> list[dict]:
    overlays = []
    for item in load_highlights(path):
        layout = layout_overlay_text(item.text)
        if not layout.fits:
            raise RuntimeError(
                f'Highlight will not fit safely: "{item.text}". '
                'Split or shorten it in Story Highlights before building.'
            )
        overlays.append({
            "text": layout.text,
            "start": item.start + time_offset,
            "end": item.end + time_offset,
            "position": item.position,
            "fade_duration": item.fade_duration,
            "font_divisor": layout.font_divisor,
            "fit_status": layout.fit_status,
            "fit_reason": layout.fit_reason,
        })
    return overlays
