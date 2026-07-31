import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.captions import (
    MAX_CAPTION_LINES,
    MAX_LINE_CHARACTERS,
    align_script_to_timing,
    caption_chunks,
    story_first_entries,
    wrap_caption_text,
    write_srt,
)


class CaptionSafetyTests(unittest.TestCase):
    def test_caption_chunks_preserve_every_word(self):
        script = (
            "Every AI model depends on "
            "water, energy, land, and people."
        )

        chunks = caption_chunks(script)

        reconstructed = " ".join(chunks)

        self.assertEqual(
            reconstructed,
            script,
        )

    def test_story_first_does_not_remove_words(self):
        original = (
            "I am here to ask "
            "different questions."
        )

        entries = story_first_entries(
            [
                {
                    "start": 0.0,
                    "end": 3.0,
                    "text": original,
                }
            ]
        )

        reconstructed = " ".join(
            entry["text"]
            for entry in entries
        )

        self.assertEqual(
            reconstructed,
            original,
        )

    def test_wrapped_caption_uses_two_lines_or_less(self):
        caption = (
            "Mother Earth deserves "
            "a seat at the table."
        )

        wrapped = wrap_caption_text(caption)
        lines = wrapped.splitlines()

        self.assertLessEqual(
            len(lines),
            MAX_CAPTION_LINES,
        )

        for line in lines:
            self.assertLessEqual(
                len(line),
                MAX_LINE_CHARACTERS,
            )

    def test_script_alignment_preserves_order(self):
        script = (
            "Today, here is one question. "
            "What does progress require?"
        )

        segments = [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "placeholder",
            }
        ]

        aligned = align_script_to_timing(
            script,
            segments,
        )

        reconstructed = " ".join(
            entry["text"]
            for entry in aligned
        )

        self.assertEqual(
            reconstructed,
            script,
        )

        self.assertEqual(
            aligned[0]["start"],
            0.0,
        )

        self.assertEqual(
            aligned[-1]["end"],
            5.0,
        )

    def test_written_srt_keeps_line_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = (
                Path(directory)
                / "captions.srt"
            )

            write_srt(
                [
                    {
                        "start": 0.0,
                        "end": 2.0,
                        "text": (
                            "Every AI model depends "
                            "on something."
                        ),
                    }
                ],
                destination,
            )

            contents = destination.read_text(
                encoding="utf-8"
            )

            caption_lines = [
                line
                for line in contents.splitlines()
                if line
                and "-->" not in line
                and not line.isdigit()
            ]

            self.assertLessEqual(
                len(caption_lines),
                MAX_CAPTION_LINES,
            )

            for line in caption_lines:
                self.assertLessEqual(
                    len(line),
                    MAX_LINE_CHARACTERS,
                )


if __name__ == "__main__":
    unittest.main()


class WordPopRendererTests(unittest.TestCase):
    def test_word_pop_has_no_background_box(self):
        import tempfile

        from mother_earth_studio.builder import (
            _drawtext_filter_graph,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subtitles = root / "captions.srt"

            subtitles.write_text(
                "1\n"
                "00:00:00,000 --> "
                "00:00:02,000\n"
                "Mother Earth comes first.\n",
                encoding="utf-8",
            )

            graph, word_count = (
                _drawtext_filter_graph(
                    subtitles,
                    root,
                    root / "missing-video.mp4",
                )
            )

            self.assertEqual(
                word_count,
                4,
            )

            self.assertEqual(
                graph.count("drawtext="),
                4,
            )

            self.assertNotIn(
                "box=1",
                graph,
            )

            self.assertIn(
                "borderw=3",
                graph,
            )
