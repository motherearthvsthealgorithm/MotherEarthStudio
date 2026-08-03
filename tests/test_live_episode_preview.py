from mother_earth_studio.story_highlights import StoryHighlight
from mother_earth_studio.story_highlights_editor import clamp_preview_time, preview_time_for_highlight


def test_clamp_preview_time_stays_inside_episode():
    assert clamp_preview_time(-2, 60) == 0
    assert clamp_preview_time(12.5, 60) == 12.5
    assert clamp_preview_time(80, 60) == 60


def test_preview_time_uses_highlight_midpoint():
    item = StoryHighlight("A complete thought.", 10.0, 14.0)
    assert preview_time_for_highlight(item) == 12.0
