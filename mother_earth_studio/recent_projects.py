from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List


APP_STATE_DIRECTORY = Path.home() / ".mother_earth_studio"
RECENT_PROJECTS_FILE = APP_STATE_DIRECTORY / "recent_projects.json"
MAX_RECENT_PROJECTS = 10


def _normalize(path: Path) -> str:
    return str(path.expanduser().resolve())


def load_recent_projects(
    state_file: Path = RECENT_PROJECTS_FILE,
) -> List[Path]:
    if not state_file.exists():
        return []

    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list):
        return []

    projects: List[Path] = []

    for item in raw:
        if not isinstance(item, str):
            continue

        project_path = Path(item).expanduser()

        if (
            project_path.is_dir()
            and (project_path / "project.json").is_file()
        ):
            projects.append(project_path.resolve())

    return projects


def save_recent_projects(
    projects: Iterable[Path],
    state_file: Path = RECENT_PROJECTS_FILE,
) -> None:
    normalized = []
    seen = set()

    for project in projects:
        value = _normalize(project)

        if value in seen:
            continue

        seen.add(value)
        normalized.append(value)

        if len(normalized) >= MAX_RECENT_PROJECTS:
            break

    state_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = state_file.with_suffix(
        state_file.suffix + ".tmp"
    )

    temporary_file.write_text(
        json.dumps(normalized, indent=2) + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(state_file)


def remember_project(
    project_path: Path,
    state_file: Path = RECENT_PROJECTS_FILE,
) -> List[Path]:
    normalized_project = project_path.expanduser().resolve()

    existing = load_recent_projects(state_file)

    updated = [
        normalized_project,
        *[
            path
            for path in existing
            if path.resolve() != normalized_project
        ],
    ]

    save_recent_projects(updated, state_file)

    return load_recent_projects(state_file)


def forget_missing_projects(
    state_file: Path = RECENT_PROJECTS_FILE,
) -> List[Path]:
    valid = load_recent_projects(state_file)
    save_recent_projects(valid, state_file)
    return valid
