from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .builder import probe_duration
from .slideshow import build_photo_slideshow
from .visual_timeline import VisualTimelineItem


@dataclass(frozen=True)
class PreparedVisualSource:
    path: Path
    mode: str
    generated: bool
    image_count: int = 0


def classify_visual_timeline(
    items: Sequence[VisualTimelineItem],
) -> str:
    if not items:
        raise ValueError(
            "Add at least one photo or video to the visual timeline."
        )

    image_count = sum(item.kind == "image" for item in items)
    video_count = sum(item.kind == "video" for item in items)

    if image_count == len(items):
        return "photos"

    if video_count == 1 and len(items) == 1:
        return "single_video"

    if image_count and video_count:
        raise ValueError(
            "Mixed photo and video rendering is not supported yet. "
            "Use photos only for a slideshow reel, or one video for "
            "the existing video workflow."
        )

    if video_count > 1:
        raise ValueError(
            "Multiple-video timelines are not supported yet. "
            "Use one video, or use photos only for a slideshow reel."
        )

    raise ValueError(
        "The visual timeline contains an unsupported item."
    )


def _safe_generated_name(narration: Path) -> str:
    stem = narration.stem.strip() or "episode"
    safe = "".join(
        character if character.isalnum() or character in "-_"
        else "-"
        for character in stem
    )
    safe = safe.strip("-") or "episode"
    return f"{safe}-photo-reel.mp4"


def prepare_visual_source(
    items: Sequence[VisualTimelineItem],
    narration: Path,
    cache_dir: Path,
    *,
    ffmpeg_path: str = "ffmpeg",
) -> PreparedVisualSource:
    mode = classify_visual_timeline(items)

    if mode == "single_video":
        video = Path(items[0].path).expanduser()

        if not video.is_file():
            raise FileNotFoundError(
                f"Timeline video does not exist: {video}"
            )

        return PreparedVisualSource(
            path=video.resolve(),
            mode=mode,
            generated=False,
        )

    images = [Path(item.path).expanduser() for item in items]

    missing = [path for path in images if not path.is_file()]

    if missing:
        raise FileNotFoundError(
            f"Timeline image does not exist: {missing[0]}"
        )

    narration = narration.expanduser()

    if not narration.is_file():
        raise FileNotFoundError(
            f"Narration does not exist: {narration}"
        )

    cache_dir = cache_dir.expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    output = cache_dir / _safe_generated_name(narration)

    narration_duration = probe_duration(narration)
    final_duration = narration_duration + 1.5

    def runner(command, **kwargs):
        adjusted = list(command)
        adjusted[0] = ffmpeg_path
        import subprocess
        return subprocess.run(adjusted, **kwargs)

    build_photo_slideshow(
        images,
        output,
        final_duration,
        runner=runner,
    )

    return PreparedVisualSource(
        path=output.resolve(),
        mode=mode,
        generated=True,
        image_count=len(images),
    )
