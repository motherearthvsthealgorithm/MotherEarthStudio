import json
import tempfile
import unittest
from pathlib import Path

from mother_earth_studio.recent_projects import (
    load_recent_projects,
    remember_project,
    save_recent_projects,
)


class RecentProjectTests(unittest.TestCase):
    def make_project(self, root: Path, name: str) -> Path:
        project = root / name
        project.mkdir()
        (project / "project.json").write_text(
            json.dumps({"title": name}),
            encoding="utf-8",
        )
        return project

    def test_remember_project_places_latest_first(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            state_file = root / "state" / "recent.json"

            first = self.make_project(root, "first")
            second = self.make_project(root, "second")

            remember_project(first, state_file)
            projects = remember_project(second, state_file)

            self.assertEqual(
                projects,
                [second.resolve(), first.resolve()],
            )

    def test_duplicate_projects_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            state_file = root / "recent.json"
            project = self.make_project(root, "episode")

            save_recent_projects(
                [project, project, project],
                state_file,
            )

            self.assertEqual(
                load_recent_projects(state_file),
                [project.resolve()],
            )

    def test_missing_projects_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            state_file = root / "recent.json"

            missing = root / "missing"

            state_file.write_text(
                json.dumps([str(missing)]),
                encoding="utf-8",
            )

            self.assertEqual(
                load_recent_projects(state_file),
                [],
            )


if __name__ == "__main__":
    unittest.main()
