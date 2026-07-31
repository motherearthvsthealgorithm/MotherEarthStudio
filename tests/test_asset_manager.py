import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.asset_manager import (
    AssetNotFoundError,
    UnsupportedAssetKeyError,
    import_asset,
    remove_asset_reference,
)
from mother_earth_studio.project import create_project


class AssetManagerTests(unittest.TestCase):
    def test_import_asset_copies_file_and_updates_project(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "forest.mp4"
            source.write_bytes(b"forest-video")

            project = create_project(
                "Asset Test",
                root / "projects",
            )

            result = import_asset(
                project,
                source,
                "video",
            )

            self.assertTrue(result.path.exists())
            self.assertEqual(
                result.relative_path,
                "assets/forest.mp4",
            )
            self.assertEqual(
                project.metadata["files"]["video"],
                "assets/forest.mp4",
            )
            self.assertEqual(
                len(project.metadata["assets"]),
                1,
            )

    def test_identical_asset_is_reused(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "narration.wav"
            source.write_bytes(b"same-audio")

            project = create_project(
                "Duplicate Test",
                root / "projects",
            )

            first = import_asset(
                project,
                source,
                "narration",
            )

            second = import_asset(
                project,
                source,
                "narration",
            )

            self.assertEqual(
                second.status,
                "existing",
            )
            self.assertEqual(
                second.path,
                first.path,
            )
            self.assertEqual(
                len(project.metadata["assets"]),
                1,
            )

    def test_same_filename_with_different_content_is_renamed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            first_folder = root / "first"
            second_folder = root / "second"
            first_folder.mkdir()
            second_folder.mkdir()

            first_source = first_folder / "music.mp3"
            second_source = second_folder / "music.mp3"

            first_source.write_bytes(b"first-track")
            second_source.write_bytes(b"second-track")

            project = create_project(
                "Collision Test",
                root / "projects",
            )

            first = import_asset(
                project,
                first_source,
                "music",
            )

            second = import_asset(
                project,
                second_source,
                "music",
            )

            self.assertEqual(
                first.path.name,
                "music.mp3",
            )
            self.assertEqual(
                second.path.name,
                "music-2.mp3",
            )
            self.assertEqual(
                second.status,
                "renamed",
            )
            self.assertEqual(
                len(project.metadata["assets"]),
                2,
            )

    def test_captions_are_stored_in_captions_folder(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "captions.srt"
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                encoding="utf-8",
            )

            project = create_project(
                "Caption Test",
                root / "projects",
            )

            result = import_asset(
                project,
                source,
                "captions",
            )

            self.assertEqual(
                result.relative_path,
                "captions/captions.srt",
            )
            self.assertEqual(
                project.metadata["files"]["captions"],
                "captions/captions.srt",
            )

    def test_remove_asset_reference_keeps_imported_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "music.mp3"
            source.write_bytes(b"music")

            project = create_project(
                "Remove Reference",
                root / "projects",
            )

            result = import_asset(
                project,
                source,
                "music",
            )

            remove_asset_reference(
                project,
                "music",
            )

            self.assertIsNone(
                project.metadata["files"]["music"]
            )
            self.assertTrue(result.path.exists())

    def test_missing_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            project = create_project(
                "Missing Test",
                root / "projects",
            )

            with self.assertRaises(AssetNotFoundError):
                import_asset(
                    project,
                    root / "missing.mp4",
                    "video",
                )

    def test_unsupported_asset_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "file.bin"
            source.write_bytes(b"content")

            project = create_project(
                "Unsupported Test",
                root / "projects",
            )

            with self.assertRaises(
                UnsupportedAssetKeyError
            ):
                import_asset(
                    project,
                    source,
                    "unknown",
                )


if __name__ == "__main__":
    unittest.main()
