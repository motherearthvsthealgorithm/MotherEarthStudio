from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal


VisualKind = Literal["image", "video"]


@dataclass(frozen=True)
class VisualTimelineItem:
    path: str
    kind: VisualKind
    order: int
    duration: float | None = None
    loop: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


SUPPORTED_IMAGE_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
}
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v"}


def detect_visual_kind(path: Path) -> VisualKind:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return "image"
    if suffix in SUPPORTED_VIDEO_SUFFIXES:
        return "video"
    raise ValueError(
        f"Unsupported visual asset type: {suffix or '(none)'}. "
        "Use JPG, PNG, WEBP, BMP, TIFF, MP4, MOV, or M4V."
    )


def normalize_visual_items(paths: Iterable[Path]) -> list[VisualTimelineItem]:
    items: list[VisualTimelineItem] = []
    for index, raw_path in enumerate(paths):
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Visual asset does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Visual asset is not a file: {path}")
        items.append(
            VisualTimelineItem(
                path=str(path.resolve()),
                kind=detect_visual_kind(path),
                order=index,
            )
        )
    if not items:
        raise ValueError("Add at least one photo or video to the visual timeline.")
    return items


def reorder_visual_items(
    items: list[VisualTimelineItem],
    source_index: int,
    destination_index: int,
) -> list[VisualTimelineItem]:
    if not items:
        return []
    if not 0 <= source_index < len(items):
        raise IndexError("source_index is outside the timeline.")
    if not 0 <= destination_index < len(items):
        raise IndexError("destination_index is outside the timeline.")
    reordered = list(items)
    moved = reordered.pop(source_index)
    reordered.insert(destination_index, moved)
    return [
        VisualTimelineItem(
            path=item.path,
            kind=item.kind,
            order=index,
            duration=item.duration,
            loop=item.loop,
        )
        for index, item in enumerate(reordered)
    ]


def remove_visual_item(
    items: list[VisualTimelineItem],
    index: int,
) -> list[VisualTimelineItem]:
    if not 0 <= index < len(items):
        raise IndexError("index is outside the timeline.")
    remaining = [
        item for item_index, item in enumerate(items)
        if item_index != index
    ]
    return [
        VisualTimelineItem(
            path=item.path,
            kind=item.kind,
            order=new_index,
            duration=item.duration,
            loop=item.loop,
        )
        for new_index, item in enumerate(remaining)
    ]


def serialize_visual_timeline(
    items: list[VisualTimelineItem],
) -> list[dict]:
    return [
        item.to_dict()
        for item in sorted(items, key=lambda item: item.order)
    ]


def deserialize_visual_timeline(
    records: Iterable[dict],
) -> list[VisualTimelineItem]:
    items: list[VisualTimelineItem] = []
    for index, record in enumerate(records):
        path = str(record.get("path", "")).strip()
        if not path:
            raise ValueError(f"Visual timeline item {index + 1} has no path.")
        kind = str(record.get("kind", "")).strip().lower()
        if kind not in {"image", "video"}:
            kind = detect_visual_kind(Path(path))
        duration_value = record.get("duration")
        duration = None if duration_value in {None, ""} else float(duration_value)
        items.append(
            VisualTimelineItem(
                path=path,
                kind=kind,
                order=index,
                duration=duration,
                loop=bool(record.get("loop", False)),
            )
        )
    return items
