import json
from pathlib import Path

import pytest

from mother_earth_studio.overlay_timeline import build_overlay_timeline


def test_story_highlights_are_primary_overlay_source(tmp_path: Path):
    source = tmp_path / "story_highlights.json"
    source.write_text(json.dumps({
        "version": 2,
        "type": "mother-earth-story-highlights",
        "source": "test.srt",
        "highlights": [{
            "text": "The forest remembers.",
            "start": 1.0,
            "end": 4.0,
            "position": "lower_center",
            "fade_duration": 0.28,
            "enabled": True,
            "confidence": 0.95,
            "review_reason": "",
        }],
    }))
    timeline = build_overlay_timeline(source, time_offset=4.5)
    assert timeline.source_kind == "story_highlights"
    assert timeline.renderer_name == "Story Highlights overlay timeline"
    assert timeline.overlays[0]["start"] == pytest.approx(5.5)


def test_srt_remains_supported_as_fallback(tmp_path: Path):
    source = tmp_path / "transcript.srt"
    source.write_text("1\n00:00:01,000 --> 00:00:04,000\nThe forest remembers.\n")
    timeline = build_overlay_timeline(
        source,
        srt_cues=[(1.0, 4.0, "The forest remembers.")],
        time_offset=4.5,
    )
    assert timeline.source_kind == "srt_fallback"
    assert timeline.overlays


def test_unsupported_overlay_source_is_rejected(tmp_path: Path):
    source = tmp_path / "captions.txt"
    source.write_text("hello")
    with pytest.raises(RuntimeError, match="story_highlights.json"):
        build_overlay_timeline(source)
