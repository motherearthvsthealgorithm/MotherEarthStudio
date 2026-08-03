from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mother_earth_studio.timeline_build import (
    classify_visual_timeline,
    prepare_visual_source,
)
from mother_earth_studio.visual_timeline import VisualTimelineItem


class TimelineBuildTests(unittest.TestCase):
    def test_photo_only_timeline_is_supported(self):
        items = [
            VisualTimelineItem(
                path="/tmp/one.jpg",
                kind="image",
                order=0,
            ),
            VisualTimelineItem(
                path="/tmp/two.jpg",
                kind="image",
                order=1,
            ),
        ]

        self.assertEqual(
            classify_visual_timeline(items),
            "photos",
        )

    def test_single_video_timeline_is_supported(self):
        items = [
            VisualTimelineItem(
                path="/tmp/forest.mp4",
                kind="video",
                order=0,
            )
        ]

        self.assertEqual(
            classify_visual_timeline(items),
            "single_video",
        )

    def test_mixed_timeline_is_rejected_clearly(self):
        items = [
            VisualTimelineItem(
                path="/tmp/one.jpg",
                kind="image",
                order=0,
            ),
            VisualTimelineItem(
                path="/tmp/forest.mp4",
                kind="video",
                order=1,
            ),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "Mixed photo and video rendering",
        ):
            classify_visual_timeline(items)

    def test_multiple_videos_are_rejected_clearly(self):
        items = [
            VisualTimelineItem(
                path="/tmp/one.mp4",
                kind="video",
                order=0,
            ),
            VisualTimelineItem(
                path="/tmp/two.mp4",
                kind="video",
                order=1,
            ),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "Multiple-video timelines",
        ):
            classify_visual_timeline(items)

    def test_single_video_returns_existing_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "forest.mp4"
            narration = root / "narration.m4a"
            video.write_bytes(b"video")
            narration.write_bytes(b"audio")

            result = prepare_visual_source(
                [
                    VisualTimelineItem(
                        path=str(video),
                        kind="video",
                        order=0,
                    )
                ],
                narration,
                root / "cache",
            )

            self.assertEqual(result.path, video.resolve())
            self.assertFalse(result.generated)
            self.assertEqual(result.mode, "single_video")

    def test_photo_timeline_builds_generated_reel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "one.jpg"
            second = root / "two.jpg"
            narration = root / "narration.m4a"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            narration.write_bytes(b"audio")

            def fake_slideshow(
                images,
                output,
                duration,
                **kwargs,
            ):
                self.assertEqual(len(images), 2)
                self.assertEqual(duration, 11.5)
                output.write_bytes(b"generated video")

            with (
                patch(
                    "mother_earth_studio.timeline_build.probe_duration",
                    return_value=10.0,
                ),
                patch(
                    "mother_earth_studio.timeline_build.build_photo_slideshow",
                    side_effect=fake_slideshow,
                ),
            ):
                result = prepare_visual_source(
                    [
                        VisualTimelineItem(
                            path=str(first),
                            kind="image",
                            order=0,
                        ),
                        VisualTimelineItem(
                            path=str(second),
                            kind="image",
                            order=1,
                        ),
                    ],
                    narration,
                    root / "cache",
                )

            self.assertTrue(result.generated)
            self.assertEqual(result.image_count, 2)
            self.assertTrue(result.path.exists())


if __name__ == "__main__":
    unittest.main()
