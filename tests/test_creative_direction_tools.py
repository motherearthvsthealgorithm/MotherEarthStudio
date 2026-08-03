from mother_earth_studio.story_highlights import (
    StoryHighlight,
    assess_highlight_confidence,
    quick_rewrite_text,
    save_highlights,
    load_highlights,
)


def test_fragment_is_low_confidence():
    score, reason = assess_highlight_confidence("it came from?", 52.31, 54.71)
    assert score < 0.70
    assert reason


def test_complete_thought_is_high_confidence():
    score, _ = assess_highlight_confidence(
        "Nature doesn't pretend nothing happened.", 26.75, 29.53
    )
    assert score >= 0.70


def test_quick_rewrite_capitalizes_and_punctuates():
    assert quick_rewrite_text("it came from") == "It came from."


def test_confidence_round_trip(tmp_path):
    path = tmp_path / "story_highlights.json"
    save_highlights(path, [StoryHighlight("A complete thought.", 1, 4, confidence=0.81)])
    loaded = load_highlights(path)
    assert loaded[0].confidence == 0.81
