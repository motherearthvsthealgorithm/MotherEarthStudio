from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .project import EpisodeProject, ProjectError


SUPPORTED_ASSET_KEYS = {
    "video",
    "narration",
    "music",
    "captions",
}


class AssetError(ProjectError):
    """Base exception for project asset errors."""


class AssetNotFoundError(AssetError):
    """Raised when an imported source file does not exist."""


class UnsupportedAssetKeyError(AssetError):
    """Raised when an unsupported project asset key is used."""


@dataclass(frozen=True)
class AssetImportResult:
    path: Path
    relative_path: str
    status: str
    checksum: str

    @property
    def imported(self) -> bool:
        return self.status in {"imported", "renamed"}

    @property
    def reused_existing(self) -> bool:
        return self.status == "existing"


def file_checksum(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _asset_records(
    project: EpisodeProject,
) -> list[Dict[str, Any]]:
    records = project.metadata.setdefault("assets", [])

    if not isinstance(records, list):
        records = []
        project.metadata["assets"] = records

    return records


def _existing_record_by_checksum(
    records: Iterable[Dict[str, Any]],
    checksum: str,
) -> Optional[Dict[str, Any]]:
    for record in records:
        if record.get("checksum") == checksum:
            return record

    return None


def _collision_safe_destination(
    folder: Path,
    filename: str,
) -> Path:
    destination = folder / filename

    if not destination.exists():
        return destination

    source_name = Path(filename)
    stem = source_name.stem
    suffix = source_name.suffix

    counter = 2

    while True:
        candidate = folder / f"{stem}-{counter}{suffix}"

        if not candidate.exists():
            return candidate

        counter += 1


def import_asset(
    project: EpisodeProject,
    source_path: Path,
    asset_key: str,
) -> AssetImportResult:
    if asset_key not in SUPPORTED_ASSET_KEYS:
        raise UnsupportedAssetKeyError(
            f"Unsupported project asset key: {asset_key}"
        )

    source = source_path.expanduser().resolve()

    if not source.is_file():
        raise AssetNotFoundError(
            f"Asset file does not exist: {source}"
        )

    checksum = file_checksum(source)
    records = _asset_records(project)

    existing_record = _existing_record_by_checksum(
        records,
        checksum,
    )

    if existing_record is not None:
        existing_relative_path = str(
            existing_record["path"]
        )

        existing_path = project.resolve(
            existing_relative_path
        )

        if existing_path.exists():
            project.set_file(
                asset_key,
                existing_path,
            )

            return AssetImportResult(
                path=existing_path,
                relative_path=existing_relative_path,
                status="existing",
                checksum=checksum,
            )

    destination_folder = (
        project.root / "captions"
        if asset_key == "captions"
        else project.root / "assets"
    )

    destination_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    preferred_destination = (
        destination_folder / source.name
    )

    destination = _collision_safe_destination(
        destination_folder,
        source.name,
    )

    status = (
        "imported"
        if destination == preferred_destination
        else "renamed"
    )

    if source != destination.resolve():
        shutil.copy2(source, destination)

    relative_path = project.relative_path(destination)

    record: Dict[str, Any] = {
        "path": relative_path,
        "original_name": source.name,
        "checksum": checksum,
        "size": destination.stat().st_size,
        "kind": asset_key,
    }

    records.append(record)

    project.metadata.setdefault(
        "files",
        {},
    )[asset_key] = relative_path

    project.save()

    return AssetImportResult(
        path=destination.resolve(),
        relative_path=relative_path,
        status=status,
        checksum=checksum,
    )


def remove_asset_reference(
    project: EpisodeProject,
    asset_key: str,
) -> None:
    if asset_key not in SUPPORTED_ASSET_KEYS:
        raise UnsupportedAssetKeyError(
            f"Unsupported project asset key: {asset_key}"
        )

    project.set_file(asset_key, None)
