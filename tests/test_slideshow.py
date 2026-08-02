from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mother_earth_studio.slideshow import (
    build_photo_slideshow,
    build_slideshow_command,
    calculate_seconds_per_image,
    validate_images,
    write_concat_file,
)


class SlideshowTests(unittest.TestCase):
    def test_seconds_are_distributed_across_images(self):
        self.assertEqual(calculate_seconds_per_image(4, 12.0), 3.0)

    def test_seconds_respect_minimum(self):
        self.assertEqual(calculate_seconds_per_image(20, 10.0), 1.0)

    def test_empty_image_list_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_images([])

    def test_unsupported_image_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notes.txt"
            path.write_text("not an image", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_images([path])

    def test_concat_file_repeats_final_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            destination = root / "slides.ffconcat"
            write_concat_file(
                [first.resolve(), second.resolve()],
                destination,
                2.5,
            )
            text = destination.read_text(encoding="utf-8")
            self.assertEqual(text.count(str(second.resolve())), 2)
            self.assertEqual(text.count("duration 2.500000"), 2)

    def test_command_builds_vertical_h264_video(self):
        command = build_slideshow_command(
            Path("/tmp/slides.ffconcat"),
            Path("/tmp/output.mp4"),
            15.0,
        )
        joined = " ".join(command)
        self.assertIn("scale=1080:1920", joined)
        self.assertIn("crop=1080:1920", joined)
        self.assertIn("libx264", command)
        self.assertIn("yuv420p", command)

    def test_build_uses_runner_and_returns_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.png"
            output = root / "slideshow.mp4"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            calls = []

            def fake_runner(command, **kwargs):
                calls.append((command, kwargs))
                output.write_bytes(b"fake mp4")
                return SimpleNamespace(
                    returncode=0, stdout="", stderr=""
                )

            result = build_photo_slideshow(
                [first, second], output, 8.0, runner=fake_runner
            )
            self.assertEqual(result.image_count, 2)
            self.assertEqual(result.seconds_per_image, 4.0)
            self.assertEqual(result.transition, "cut")
            self.assertEqual(len(calls), 1)
            self.assertTrue(output.exists())

    def test_build_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "first.jpg"
            output = root / "slideshow.mp4"
            image.write_bytes(b"first")

            def failed_runner(command, **kwargs):
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="simulated ffmpeg failure",
                )

            with self.assertRaisesRegex(
                RuntimeError, "simulated ffmpeg failure"
            ):
                build_photo_slideshow(
                    [image], output, 5.0, runner=failed_runner
                )

    def test_non_cut_transition_is_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "first.jpg"
            image.write_bytes(b"first")
            with self.assertRaisesRegex(
                ValueError, "supports transition='cut'"
            ):
                build_photo_slideshow(
                    [image],
                    Path(temp_dir) / "output.mp4",
                    5.0,
                    transition="crossfade",
                )


if __name__ == "__main__":
    unittest.main()
