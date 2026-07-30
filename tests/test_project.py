import json
import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.project import (
    InvalidProjectError,
    ProjectAlreadyExistsError,
    ProjectError,
    create_project,
    load_project,
)


class ProjectTests(unittest.TestCase):
    def test_create_project_builds_complete_structure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            projects_root = Path(temporary_directory)

            project = create_project(
                "Mother Earth Check",
                projects_root,
            )

            self.assertEqual(
                project.root.name,
                "mother-earth-check",
            )

            self.assertTrue(project.project_file.exists())
            self.assertTrue(
                (project.root / "script" / "script.md").exists()
            )

            for folder_name in (
                "assets",
                "captions",
                "exports",
                "publishing",
                "notes",
            ):
                self.assertTrue(
                    (project.root / folder_name).is_dir()
                )

            metadata = json.loads(
                project.project_file.read_text(encoding="utf-8")
            )

            self.assertEqual(
                metadata["title"],
                "Mother Earth Check",
            )

            self.assertEqual(
                metadata["version"],
                "0.10.0",
            )

            self.assertEqual(
                metadata["files"]["script"],
                "script/script.md",
            )

    def test_load_project_restores_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            created = create_project(
                "Future Generations",
                Path(temporary_directory),
            )

            loaded = load_project(created.root)

            self.assertEqual(
                loaded.title,
                "Future Generations",
            )

            self.assertEqual(
                loaded.root,
                created.root.resolve(),
            )

    def test_duplicate_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            projects_root = Path(temporary_directory)

            create_project("Duplicate", projects_root)

            with self.assertRaises(ProjectAlreadyExistsError):
                create_project("Duplicate", projects_root)

    def test_external_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            projects_root = temporary_root / "projects"
            external_file = temporary_root / "outside.mp4"

            external_file.write_text(
                "placeholder",
                encoding="utf-8",
            )

            project = create_project(
                "Protected Paths",
                projects_root,
            )

            with self.assertRaises(ProjectError):
                project.relative_path(external_file)

    def test_invalid_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(InvalidProjectError):
                load_project(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
