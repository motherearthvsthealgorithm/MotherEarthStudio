from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BRAND_TITLE = "Mother Earth vs. The Algorithm"
DEFAULT_TAGLINE = "I'm here to ask different questions."


@dataclass(frozen=True)
class BrandIdentity:
    enabled: bool = True
    title: str = DEFAULT_BRAND_TITLE
    tagline: str = DEFAULT_TAGLINE
    intro_duration: float = 4.5
    title_start: float = 1.0
    title_end: float = 4.0
    fade_in_duration: float = 1.0
    fade_out_duration: float = 1.0
    cinematic_grade: bool = True
    saturation: float = 0.82
    contrast: float = 0.96
    brightness: float = -0.025
    warmth: float = 0.025


def _escape_filter_path(path: Path) -> str:
    return (
        str(path.resolve())
        .replace("\\", "/")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )


def _font_file() -> Path | None:
    candidates = [
        Path("/System/Library/Fonts/NewYork.ttf"),
        Path("/System/Library/Fonts/Supplemental/Didot.ttc"),
        Path("/System/Library/Fonts/Supplemental/Hoefler Text.ttc"),
        Path("/System/Library/Fonts/Supplemental/Georgia.ttf"),
        Path("/System/Library/Fonts/HelveticaNeue.ttc"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    return next((path for path in candidates if path.exists()), None)


def create_brand_text_files(
    temp_dir: Path,
    identity: BrandIdentity,
) -> tuple[Path, Path]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    title_file = temp_dir / "brand-title.txt"
    tagline_file = temp_dir / "brand-tagline.txt"
    title_file.write_text(identity.title, encoding="utf-8")
    tagline_file.write_text(identity.tagline, encoding="utf-8")
    return title_file, tagline_file


def build_brand_filter(
    temp_dir: Path,
    final_duration: float,
    identity: BrandIdentity,
) -> str:
    if not identity.enabled:
        return ""

    title_file, tagline_file = create_brand_text_files(
        temp_dir,
        identity,
    )
    font = _font_file()
    font_option = (
        f"fontfile='{_escape_filter_path(font)}'"
        if font
        else "font='Georgia'"
    )
    title_path = _escape_filter_path(title_file)
    tagline_path = _escape_filter_path(tagline_file)
    ending_fade_start = max(
        identity.intro_duration,
        final_duration - identity.fade_out_duration,
    )

    return ",".join(
        [
            (
                "eq="
                f"brightness={identity.brightness:.3f}:"
                f"contrast={identity.contrast:.3f}:"
                f"saturation={identity.saturation:.3f}"
            ),
            (
                "colorbalance="
                f"rs={identity.warmth:.3f}:"
                f"gs={identity.warmth * 0.45:.3f}:"
                f"bs={-identity.warmth:.3f}"
            ),
            (
                "fade=t=in:st=0:"
                f"d={identity.fade_in_duration:.3f}:color=black"
            ),
            (
                "drawtext="
                f"textfile='{title_path}':reload=0:"
                f"{font_option}:expansion=none:"
                "fontcolor=0xF4F0E8:fontsize=h/27:"
                "x=(w-text_w)/2:y=h*0.42:"
                "borderw=0:shadowx=0:shadowy=0:"
                f"enable='between(t,{identity.title_start:.3f},"
                f"{identity.title_end:.3f})'"
            ),
            (
                "drawtext="
                f"textfile='{tagline_path}':reload=0:"
                f"{font_option}:expansion=none:"
                "fontcolor=0xF4F0E8@0.90:fontsize=h/53:"
                "x=(w-text_w)/2:y=h*0.49:"
                "borderw=0:shadowx=0:shadowy=0:"
                f"enable='between(t,{identity.title_start + 1.0:.3f},"
                f"{identity.title_end:.3f})'"
            ),
            (
                "fade=t=out:"
                f"st={ending_fade_start:.3f}:"
                f"d={identity.fade_out_duration:.3f}:color=black"
            ),
        ]
    )


def generate_cover(
    source: Path,
    destination: Path,
    headline: str,
    identity: BrandIdentity,
    *,
    ffmpeg_path: str = "ffmpeg",
    runner=subprocess.run,
) -> Path:
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"Cover source does not exist: {source}")

    clean_headline = " ".join(headline.split()).strip()
    if not clean_headline:
        raise ValueError("A cover headline is required.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="mother_earth_cover_"
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        headline_file = temp_dir / "headline.txt"
        brand_file = temp_dir / "brand.txt"
        headline_file.write_text(clean_headline, encoding="utf-8")
        brand_file.write_text(identity.title, encoding="utf-8")

        font = _font_file()
        font_option = (
            f"fontfile='{_escape_filter_path(font)}'"
            if font
            else "font='Georgia'"
        )
        headline_path = _escape_filter_path(headline_file)
        brand_path = _escape_filter_path(brand_file)

        filter_graph = ",".join(
            [
                (
                    "scale=1080:1920:"
                    "force_original_aspect_ratio=increase"
                ),
                "crop=1080:1920",
                (
                    "eq="
                    f"brightness={identity.brightness - 0.10:.3f}:"
                    f"contrast={identity.contrast:.3f}:"
                    f"saturation={identity.saturation:.3f}"
                ),
                (
                    "colorbalance="
                    f"rs={identity.warmth:.3f}:"
                    f"gs={identity.warmth * 0.45:.3f}:"
                    f"bs={-identity.warmth:.3f}"
                ),
                (
                    "drawtext="
                    f"textfile='{headline_path}':reload=0:"
                    f"{font_option}:expansion=none:"
                    "fontcolor=0xF4F0E8:fontsize=76:"
                    "line_spacing=14:"
                    "x=(w-text_w)/2:y=h*0.40:"
                    "borderw=0:shadowx=0:shadowy=0"
                ),
                (
                    "drawtext="
                    f"textfile='{brand_path}':reload=0:"
                    f"{font_option}:expansion=none:"
                    "fontcolor=0xF4F0E8@0.88:fontsize=32:"
                    "x=(w-text_w)/2:y=h*0.82:"
                    "borderw=0:shadowx=0:shadowy=0"
                ),
                "format=rgb24",
            ]
        )

        command = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error"]

        if source.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            command += ["-ss", "1.0", "-i", str(source)]
        else:
            command += ["-i", str(source)]

        command += [
            "-frames:v",
            "1",
            "-vf",
            filter_graph,
            str(destination),
        ]

        result = runner(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            detail = (result.stderr or "").strip()
            raise RuntimeError(
                "Cover generation failed."
                + (f"\n\n{detail}" if detail else "")
            )

    if not destination.exists():
        raise RuntimeError(
            "Cover generation completed without creating an output file."
        )

    return destination
