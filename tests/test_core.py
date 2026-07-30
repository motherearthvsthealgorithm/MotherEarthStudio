from pathlib import Path
from tempfile import TemporaryDirectory
from mother_earth_studio.builder import clean_title, next_output_path
from mother_earth_studio.captions import align_script_to_timing, srt_timestamp


def test_clean_title():
    assert clean_title("Mother Earth: A Question") == "Mother_Earth_A_Question"


def test_numbering():
    with TemporaryDirectory() as temp:
        folder = Path(temp)
        (folder / "001_First.mp4").touch()
        (folder / "004_Fourth.mp4").touch()
        number, output = next_output_path(folder, "Next")
        assert number == 5
        assert output.name == "005_Next.mp4"


def test_script_alignment_preserves_words():
    script = "Mother Earth comes first. Technology supports the story."
    segments = [{"start": 0.0, "end": 4.0, "text": "wrong transcription"}]
    aligned = align_script_to_timing(script, segments)
    assert " ".join(x["text"] for x in aligned) == script
    assert aligned[0]["start"] == 0.0
    assert aligned[-1]["end"] == 4.0


def test_timestamp():
    assert srt_timestamp(65.432) == "00:01:05,432"


def test_srt_parser_wraps_long_caption():
    from mother_earth_studio.builder import _parse_srt
    with TemporaryDirectory() as temp:
        path = Path(temp) / "captions.srt"
        path.write_text("1\n00:00:00,000 --> 00:00:07,000\nHi, this is voice memo, test number two.\n", encoding="utf-8")
        cues = _parse_srt(path)
        assert cues[0][0] == 0.0
        assert cues[0][1] == 7.0
        assert "number two." in cues[0][2]
        assert "\n" in cues[0][2]
