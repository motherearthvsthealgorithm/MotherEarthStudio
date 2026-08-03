from mother_earth_studio.story_first_caption_engine import (
    balance_two_lines,
    merge_into_thought_units,
    prepare_story_overlays,
)


def test_merges_fragments_without_random_word_popping():
    cues = [
        (0.0, 1.0, "The forest remembers"),
        (1.05, 2.2, "what we forget."),
        (2.5, 3.4, "But we can listen."),
    ]
    units = merge_into_thought_units(cues)
    assert units[0][2] == "The forest remembers what we forget."
    assert units[1][2] == "But we can listen."


def test_balances_long_text_to_two_lines():
    result = balance_two_lines("Everything we lose today changes the world we inherit tomorrow")
    assert len(result.splitlines()) == 2
    assert all(line.strip() for line in result.splitlines())


def test_overlays_use_stable_timing_and_safe_lines():
    cues = [(0.0, 2.4, "Everything we lose today changes the world we inherit tomorrow.")]
    overlays = prepare_story_overlays(cues, time_offset=4.5)
    assert overlays[0]["start"] == 4.5
    assert len(overlays[0]["text"].splitlines()) <= 3
    assert overlays[0]["end"] > overlays[0]["start"]
