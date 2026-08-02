from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


SUPPORTED_IMAGE_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
}


@dataclass(frozen=True)
class SlideshowResult:
    output: Path
    image_count: int
    duration: float
    seconds_per_image: float
    transition: str
    command: tuple[str, ...]


def validate_images(images: Iterable[Path]) -> list[Path]:
    validated: list[Path] = []
    for raw_path in images:
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Image does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Image path is not a file: {path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError(
                f"Unsupported image type: {path.suffix or '(none)'}. "
                "Use JPG, JPEG, PNG, WEBP, BMP, TIF, or TIFF."
            )
        validated.append(path.resolve())
    if not validated:
        raise ValueError("Choose at least one image for the slideshow.")
    return validated


def calculate_seconds_per_image(
    image_count: int,
    total_duration: float,
    minimum: float = 1.0,
) -> float:
    if image_count < 1:
        raise ValueError("image_count must be at least 1.")
    if total_duration <= 0:
        raise ValueError("total_duration must be greater than zero.")
    return max(minimum, total_duration / image_count)


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("'", r"'\''")


def write_concat_file(
    images: Sequence[Path],
    destination: Path,
    seconds_per_image: float,
) -> None:
    if seconds_per_image <= 0:
        raise ValueError("seconds_per_image must be greater than zero.")
    lines: list[str] = []
    for image in images:
        lines.append(f"file '{_escape_concat_path(image)}'")
        lines.append(f"duration {seconds_per_image:.6f}")
    lines.append(f"file '{_escape_concat_path(images[-1])}'")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_slideshow_command(
    concat_file: Path,
    output: Path,
    total_duration: float,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> list[str]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero.")
    if fps <= 0:
        raise ValueError("fps must be greater than zero.")
    if total_duration <= 0:
        raise ValueError("total_duration must be greater than zero.")

    visual_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )

    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-vf", visual_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-t", f"{total_duration:.3f}", str(output),
    ]


def build_photo_slideshow(
    images: Iterable[Path],
    output: Path,
    total_duration: float,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    transition: str = "cut",
    runner=subprocess.run,
) -> SlideshowResult:
    """Build a silent vertical MP4 for the existing episode pipeline."""
    normalized_transition = transition.strip().lower()
    if normalized_transition != "cut":
        raise ValueError(
            "The current slideshow foundation supports transition='cut'. "
            "Crossfade and Ken Burns are reserved for the next increment."
        )

    validated = validate_images(images)
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    seconds_per_image = calculate_seconds_per_image(
        len(validated), total_duration
    )

    with tempfile.TemporaryDirectory(
        prefix="mother_earth_slideshow_"
    ) as temp_dir:
        concat_file = Path(temp_dir) / "slides.ffconcat"
        write_concat_file(validated, concat_file, seconds_per_image)
        command = build_slideshow_command(
            concat_file,
            output,
            total_duration,
            width=width,
            height=height,
            fps=fps,
        )
        completed = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                "FFmpeg could not build the photo slideshow."
                + (f"\n\n{detail}" if detail else "")
            )

    if not output.exists():
        raise RuntimeError(
            "FFmpeg reported success, but no slideshow file was created."
        )

    return SlideshowResult(
        output=output,
        image_count=len(validated),
        duration=float(total_duration),
        seconds_per_image=seconds_per_image,
        transition=normalized_transition,
        command=tuple(command),
    )
