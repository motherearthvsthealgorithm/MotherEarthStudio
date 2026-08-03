from pathlib import Path
from mother_earth_studio.story_highlights import StoryHighlight, save_highlights, load_highlights, suggest_highlights_from_srt, render_ready_overlays

def test_round_trip(tmp_path):
    path=tmp_path/'highlights.json'
    save_highlights(path,[StoryHighlight('A meaningful thought',1,5,'lower_center',0.3)])
    loaded=load_highlights(path)
    assert loaded[0].text=='A meaningful thought'
    assert loaded[0].fade_duration==0.3

def test_suggestions_are_selective(tmp_path):
    srt=tmp_path/'captions.srt'
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nThe forest remembers.\n\n2\n00:00:02,200 --> 00:00:04,000\nWe often forget.\n\n3\n00:00:08,000 --> 00:00:11,000\nWhat does the earth ask of us?\n")
    items=suggest_highlights_from_srt(srt,maximum=2)
    assert 1 <= len(items) <= 2

def test_render_ready_balances_lines(tmp_path):
    path=tmp_path/'highlights.json'
    save_highlights(path,[StoryHighlight('The world has been leaving its mark on us',2,7)])
    overlays=render_ready_overlays(path,4.5)
    assert overlays[0]['start']==6.5
    assert '\n' in overlays[0]['text']
