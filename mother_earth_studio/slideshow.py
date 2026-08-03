from __future__ import annotations

import math
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
        raise ValueError(
            "seconds_per_image must be greater than zero."
        )
    lines: list[str] = []
    for image in images:
        lines.append(f"file '{_escape_concat_path(image)}'")
        lines.append(f"duration {seconds_per_image:.6f}")
    lines.append(f"file '{_escape_concat_path(images[-1])}'")
    destination.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def build_looped_image_sequence(
    images: Sequence[Path],
    total_duration: float,
    *,
    target_seconds_per_image: float = 3.5,
) -> tuple[list[Path], float]:
    if not images:
        raise ValueError("Choose at least one image.")
    if total_duration <= 0:
        raise ValueError(
            "total_duration must be greater than zero."
        )
    if target_seconds_per_image <= 0:
        raise ValueError(
            "target_seconds_per_image must be greater than zero."
        )

    slide_count = max(
        len(images),
        math.ceil(total_duration / target_seconds_per_image),
    )
    seconds_per_image = total_duration / slide_count
    repeated = [
        images[index % len(images)]
        for index in range(slide_count)
    ]
    return repeated, seconds_per_image


def build_slideshow_command(
    concat_file: Path,
    output: Path,
    total_duration: float,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    fade_in_seconds: float = 1.0,
    fade_out_seconds: float = 1.0,
) -> list[str]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero.")
    if fps <= 0:
        raise ValueError("fps must be greater than zero.")
    if total_duration <= 0:
        raise ValueError("total_duration must be greater than zero.")

    if fade_in_seconds < 0 or fade_out_seconds < 0:
        raise ValueError("Fade durations cannot be negative.")

    fade_out_start = max(
        fade_in_seconds,
        total_duration - fade_out_seconds,
    )
    visual_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},"
        f"fade=t=in:st=0:d={fade_in_seconds:.3f}:color=black,"
        f"fade=t=out:st={fade_out_start:.3f}:"
        f"d={fade_out_seconds:.3f}:color=black,"
        "format=yuv420p"
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
    repeated_images, seconds_per_image = (
        build_looped_image_sequence(
            validated,
            total_duration,
            target_seconds_per_image=3.5,
        )
    )

    with tempfile.TemporaryDirectory(
        prefix="mother_earth_slideshow_"
    ) as temp_dir:
        concat_file = Path(temp_dir) / "slides.ffconcat"
        write_concat_file(
            repeated_images,
            concat_file,
            seconds_per_image,
        )
        command = build_slideshow_command(
            concat_file,
            output,
            total_duration,
            width=width,
            height=height,
            fps=fps,
            fade_in_seconds=1.0,
            fade_out_seconds=1.0,
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
