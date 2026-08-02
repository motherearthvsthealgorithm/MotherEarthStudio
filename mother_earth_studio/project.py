from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_VERSION = "0.10.0"
PROJECT_FILENAME = "project.json"

DEFAULT_PROJECTS_ROOT = (
    Path.home()
    / "Documents"
    / "Mother Earth Studio Projects"
)

PROJECT_FOLDERS = (
    "script",
    "assets",
    "captions",
    "exports",
    "publishing",
    "notes",
)


class ProjectError(Exception):
    """Base exception for Mother Earth Studio project errors."""


class ProjectAlreadyExistsError(ProjectError):
    """Raised when a project folder already exists."""


class InvalidProjectError(ProjectError):
    """Raised when a folder is not a valid Studio project."""


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    return cleaned or "untitled-episode"


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    temporary_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    temporary_path.replace(path)


@dataclass
class EpisodeProject:
    root: Path
    metadata: Dict[str, Any]

    @property
    def project_file(self) -> Path:
        return self.root / PROJECT_FILENAME

    @property
    def title(self) -> str:
        return str(self.metadata.get("title", "Untitled Episode"))

    def resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        project_root = self.root.resolve()

        if candidate != project_root and project_root not in candidate.parents:
            raise ProjectError(
                "Project paths must remain inside the project folder."
            )

        return candidate

    def relative_path(self, path: Path) -> str:
        resolved_path = path.expanduser().resolve()
        project_root = self.root.resolve()

        try:
            return resolved_path.relative_to(project_root).as_posix()
        except ValueError as exc:
            raise ProjectError(
                "The selected file is outside the project folder."
            ) from exc

    def save(self) -> None:
        self.metadata["modified"] = _utc_timestamp()
        self.metadata["version"] = PROJECT_VERSION
        _write_json_atomic(self.project_file, self.metadata)

    def update_title(self, title: str) -> None:
        cleaned_title = title.strip()

        if not cleaned_title:
            raise ProjectError("Project title cannot be empty.")

        self.metadata["title"] = cleaned_title
        self.save()

    def set_file(self, key: str, path: Optional[Path]) -> None:
        if path is None:
            self.metadata["files"][key] = None
        else:
            self.metadata["files"][key] = self.relative_path(path)

        self.save()

    def file_path(self, key: str) -> Optional[Path]:
        relative_path = self.metadata.get("files", {}).get(key)

        if not relative_path:
            return None

        return self.resolve(str(relative_path))


def create_project(
    title: str,
    projects_root: Optional[Path] = None,
) -> EpisodeProject:
    cleaned_title = title.strip()

    if not cleaned_title:
        raise ProjectError("Project title cannot be empty.")

    root_directory = (
        projects_root.expanduser()
        if projects_root
        else DEFAULT_PROJECTS_ROOT
    )

    root_directory.mkdir(parents=True, exist_ok=True)

    project_root = root_directory / _slugify(cleaned_title)

    if project_root.exists():
        raise ProjectAlreadyExistsError(
            f"A project already exists at: {project_root}"
        )

    project_root.mkdir()

    for folder_name in PROJECT_FOLDERS:
        (project_root / folder_name).mkdir()

    script_path = project_root / "script" / "script.md"
    script_path.write_text(
        f"# {cleaned_title}\n\n",
        encoding="utf-8",
    )

    timestamp = _utc_timestamp()

    metadata: Dict[str, Any] = {
        "title": cleaned_title,
        "version": PROJECT_VERSION,
        "created": timestamp,
        "modified": timestamp,
        "files": {
            "script": "script/script.md",
            "video": None,
            "narration": None,
            "music": None,
            "captions": None,
        },
        "visual_timeline": [],
        "exports": [],
        "publishing": {},
    }

    project = EpisodeProject(
        root=project_root,
        metadata=metadata,
    )

    _write_json_atomic(project.project_file, metadata)

    return project


def load_project(project_path: Path) -> EpisodeProject:
    expanded_path = project_path.expanduser()

    if expanded_path.is_file():
        project_file = expanded_path
        project_root = expanded_path.parent
    else:
        project_root = expanded_path
        project_file = project_root / PROJECT_FILENAME

    if not project_file.exists():
        raise InvalidProjectError(
            f"No {PROJECT_FILENAME} was found at: {project_root}"
        )

    try:
        metadata = json.loads(
            project_file.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidProjectError(
            f"Could not read project metadata: {project_file}"
        ) from exc

    required_fields = {
        "title",
        "version",
        "created",
        "modified",
        "files",
    }

    missing_fields = required_fields.difference(metadata)

    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise InvalidProjectError(
            f"Project metadata is missing: {missing}"
        )

    return EpisodeProject(
        root=project_root.resolve(),
        metadata=metadata,
    )
