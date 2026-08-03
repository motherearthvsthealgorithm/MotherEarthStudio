from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.brand_identity import (
    BrandIdentity,
    build_brand_filter,
    generate_cover,
)


class Completed:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


class BrandIdentityTests(unittest.TestCase):
    def test_default_identity_matches_locked_brand(self):
        identity = BrandIdentity()

        self.assertEqual(
            identity.title,
            "Mother Earth vs. The Algorithm",
        )
        self.assertEqual(
            identity.tagline,
            "I'm here to ask different questions.",
        )
        self.assertEqual(identity.intro_duration, 4.5)

    def test_filter_contains_title_tagline_and_ending_fade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph = build_brand_filter(
                Path(temp_dir),
                25.0,
                BrandIdentity(),
            )

            self.assertIn("drawtext=", graph)
            self.assertIn("fade=t=in", graph)
            self.assertIn("fade=t=out", graph)
            self.assertIn("saturation=0.820", graph)
            self.assertIn("fontcolor=0xF4F0E8", graph)
            self.assertIn("between(t,1.000,4.000)", graph)

    def test_disabled_brand_returns_empty_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph = build_brand_filter(
                Path(temp_dir),
                25.0,
                BrandIdentity(enabled=False),
            )

            self.assertEqual(graph, "")

    def test_cover_command_builds_vertical_png(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.jpg"
            output = root / "cover.png"
            source.write_bytes(b"image")
            commands = []

            def runner(command, **kwargs):
                commands.append(command)
                output.write_bytes(b"png")
                return Completed()

            result = generate_cover(
                source,
                output,
                "Different Questions",
                BrandIdentity(),
                runner=runner,
            )

            joined = " ".join(commands[0])
            self.assertEqual(result, output.resolve())
            self.assertIn("scale=1080:1920", joined)
            self.assertIn("drawtext=", joined)

    def test_cover_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "cover.png"

            with self.assertRaises(FileNotFoundError):
                generate_cover(
                    Path(temp_dir) / "missing.jpg",
                    output,
                    "Headline",
                    BrandIdentity(),
                )

    def test_cover_rejects_empty_headline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.jpg"
            source.write_bytes(b"image")

            with self.assertRaises(ValueError):
                generate_cover(
                    source,
                    Path(temp_dir) / "cover.png",
                    "   ",
                    BrandIdentity(),
                )


if __name__ == "__main__":
    unittest.main()
