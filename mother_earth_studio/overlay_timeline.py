from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .story_first_caption_engine import (
    DEFAULT_STORY_CAPTION_STYLE,
    prepare_story_overlays,
)
from .story_highlights import render_ready_overlays

SUPPORTED_OVERLAY_SUFFIXES = {".json", ".srt"}


@dataclass(frozen=True)
class OverlayTimeline:
    source: Path
    source_kind: str
    overlays: list[dict]

    @property
    def renderer_name(self) -> str:
        if self.source_kind == "story_highlights":
            return "Story Highlights overlay timeline"
        return "Transcript fallback overlay timeline"


def build_overlay_timeline(
    source: Path,
    *,
    srt_cues: list[tuple[float, float, str]] | None = None,
    time_offset: float = 0.0,
) -> OverlayTimeline:
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_OVERLAY_SUFFIXES:
        raise RuntimeError(
            "Text overlays must be a Mother Earth Studio story_highlights.json "
            "file or a standard .srt transcript."
        )

    if suffix == ".json":
        overlays = render_ready_overlays(source, time_offset=time_offset)
        source_kind = "story_highlights"
    else:
        if srt_cues is None:
            raise RuntimeError("SRT overlay conversion requires parsed transcript cues.")
        overlays = prepare_story_overlays(
            srt_cues,
            time_offset=time_offset,
            style=DEFAULT_STORY_CAPTION_STYLE,
        )
        source_kind = "srt_fallback"

    if not overlays:
        raise RuntimeError("The selected text-overlay source contains no renderable overlays.")

    return OverlayTimeline(source, source_kind, overlays)
