from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.visual_timeline import (
    VisualTimelineItem,
    deserialize_visual_timeline,
    detect_visual_kind,
    normalize_visual_items,
    remove_visual_item,
    reorder_visual_items,
    serialize_visual_timeline,
)


class VisualTimelineTests(unittest.TestCase):
    def test_detects_image_kind(self):
        self.assertEqual(detect_visual_kind(Path("photo.jpg")), "image")

    def test_detects_video_kind(self):
        self.assertEqual(detect_visual_kind(Path("clip.mp4")), "video")

    def test_rejects_unsupported_visual_type(self):
        with self.assertRaises(ValueError):
            detect_visual_kind(Path("notes.txt"))

    def test_normalizes_mixed_visual_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "photo.jpg"
            video = root / "clip.mp4"
            photo.write_bytes(b"photo")
            video.write_bytes(b"video")
            items = normalize_visual_items([photo, video])
            self.assertEqual([item.kind for item in items], ["image", "video"])
            self.assertEqual([item.order for item in items], [0, 1])

    def test_empty_timeline_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_visual_items([])

    def test_reorder_reindexes_items(self):
        items = [
            VisualTimelineItem(path="/tmp/one.jpg", kind="image", order=0),
            VisualTimelineItem(path="/tmp/two.mp4", kind="video", order=1),
        ]
        reordered = reorder_visual_items(items, 1, 0)
        self.assertEqual(reordered[0].path, "/tmp/two.mp4")
        self.assertEqual([item.order for item in reordered], [0, 1])

    def test_remove_reindexes_items(self):
        items = [
            VisualTimelineItem(path="/tmp/one.jpg", kind="image", order=0),
            VisualTimelineItem(path="/tmp/two.jpg", kind="image", order=1),
            VisualTimelineItem(path="/tmp/three.mp4", kind="video", order=2),
        ]
        remaining = remove_visual_item(items, 1)
        self.assertEqual(
            [item.path for item in remaining],
            ["/tmp/one.jpg", "/tmp/three.mp4"],
        )
        self.assertEqual([item.order for item in remaining], [0, 1])

    def test_serialization_preserves_order(self):
        items = [
            VisualTimelineItem(path="/tmp/two.mp4", kind="video", order=1),
            VisualTimelineItem(path="/tmp/one.jpg", kind="image", order=0),
        ]
        records = serialize_visual_timeline(items)
        self.assertEqual(
            [record["path"] for record in records],
            ["/tmp/one.jpg", "/tmp/two.mp4"],
        )

    def test_deserialization_restores_items(self):
        records = [
            {
                "path": "/tmp/one.jpg",
                "kind": "image",
                "order": 8,
                "duration": 2.5,
                "loop": False,
            },
            {
                "path": "/tmp/two.mp4",
                "kind": "video",
                "order": 4,
                "duration": None,
                "loop": True,
            },
        ]
        items = deserialize_visual_timeline(records)
        self.assertEqual([item.order for item in items], [0, 1])
        self.assertEqual(items[0].duration, 2.5)
        self.assertTrue(items[1].loop)


if __name__ == "__main__":
    unittest.main()
