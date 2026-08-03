from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.slideshow import (
    build_looped_image_sequence,
    build_slideshow_command,
    write_concat_file,
)


class SlideshowBugfixTests(unittest.TestCase):
    def test_looped_sequence_targets_shorter_slide_duration(self):
        images = [
            Path("/tmp/one.jpg"),
            Path("/tmp/two.jpg"),
            Path("/tmp/three.jpg"),
        ]

        sequence, seconds = build_looped_image_sequence(
            images,
            20.0,
            target_seconds_per_image=3.5,
        )

        self.assertGreater(len(sequence), len(images))
        self.assertLessEqual(seconds, 3.5)
        self.assertEqual(sequence[:3], images)
        self.assertEqual(sequence[3], images[0])

    def test_looped_sequence_fills_total_duration(self):
        images = [Path("/tmp/one.jpg"), Path("/tmp/two.jpg")]

        sequence, seconds = build_looped_image_sequence(
            images,
            12.0,
        )

        self.assertAlmostEqual(
            len(sequence) * seconds,
            12.0,
            places=5,
        )

    def test_command_uses_native_fades_without_ppm_input(self):
        command = build_slideshow_command(
            Path("/tmp/slides.ffconcat"),
            Path("/tmp/output.mp4"),
            20.0,
        )
        joined = " ".join(command)

        self.assertIn("fade=t=in", joined)
        self.assertIn("fade=t=out", joined)
        self.assertNotIn(".ppm", joined)

    def test_concat_contains_only_supplied_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "slides.ffconcat"
            images = [
                Path("/tmp/one.jpg"),
                Path("/tmp/two.jpg"),
                Path("/tmp/one.jpg"),
            ]

            write_concat_file(images, destination, 3.0)
            text = destination.read_text(encoding="utf-8")

            self.assertNotIn(".ppm", text)
            self.assertEqual(text.count("file '"), 4)


if __name__ == "__main__":
    unittest.main()
