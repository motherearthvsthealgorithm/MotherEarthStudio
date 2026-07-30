import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class SystemStatus:
    ffmpeg: bool
    ffprobe: bool
    subtitles_filter: bool
    drawtext_filter: bool
    whisper: bool
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None
    ass_filter: bool = False

    @property
    def can_build(self) -> bool:
        return self.ffmpeg and self.ffprobe

    @property
    def can_burn_captions(self) -> bool:
        return self.subtitles_filter or self.drawtext_filter


def _unique_existing(candidates: Iterable[Optional[str]]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        expanded = str(Path(candidate).expanduser())
        if expanded in seen:
            continue
        seen.add(expanded)
        if Path(expanded).is_file() and os.access(expanded, os.X_OK):
            results.append(expanded)
    return results


def _candidate_ffmpeg_paths() -> list[str]:
    """Return candidates in preferred order, favoring full-featured Homebrew builds."""
    env_override = os.environ.get("MOTHER_EARTH_FFMPEG")
    path_ffmpeg = shutil.which("ffmpeg")
    return _unique_existing(
        [
            env_override,
            "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",  # Apple Silicon Homebrew
            "/usr/local/opt/ffmpeg-full/bin/ffmpeg",    # Intel Homebrew
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            path_ffmpeg,
        ]
    )


def _filters_for(executable: str) -> str:
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return "\n".join(part for part in (result.stdout, result.stderr) if part)
    except (OSError, subprocess.SubprocessError):
        return ""


def _has_filter(filters: str, name: str) -> bool:
    # FFmpeg's filter table contains one filter per line. Token matching avoids
    # false positives from unrelated diagnostic prose.
    return any(name in line.split() for line in filters.splitlines())


def find_best_ffmpeg() -> tuple[Optional[str], str]:
    """Choose the most capable FFmpeg, preferring caption-capable candidates."""
    candidates = _candidate_ffmpeg_paths()
    if not candidates:
        return None, ""

    first_working: tuple[Optional[str], str] = (None, "")
    for executable in candidates:
        filters = _filters_for(executable)
        if not filters:
            continue
        if first_working[0] is None:
            first_working = (executable, filters)
        if _has_filter(filters, "drawtext") and (
            _has_filter(filters, "subtitles") or _has_filter(filters, "ass")
        ):
            return executable, filters
    return first_working


def _matching_ffprobe(ffmpeg_path: Optional[str]) -> Optional[str]:
    override = os.environ.get("MOTHER_EARTH_FFPROBE")
    candidates: list[Optional[str]] = [override]
    if ffmpeg_path:
        candidates.append(str(Path(ffmpeg_path).with_name("ffprobe")))
    candidates.extend(
        [
            "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe",
            "/usr/local/opt/ffmpeg-full/bin/ffprobe",
            shutil.which("ffprobe"),
        ]
    )
    paths = _unique_existing(candidates)
    return paths[0] if paths else None


def check_system() -> SystemStatus:
    ffmpeg_path, filters = find_best_ffmpeg()
    ffprobe_path = _matching_ffprobe(ffmpeg_path)

    try:
        import whisper  # noqa: F401
        whisper_ok = True
    except Exception:
        whisper_ok = False

    return SystemStatus(
        ffmpeg=bool(ffmpeg_path),
        ffprobe=bool(ffprobe_path),
        subtitles_filter=_has_filter(filters, "subtitles"),
        drawtext_filter=_has_filter(filters, "drawtext"),
        whisper=whisper_ok,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        ass_filter=_has_filter(filters, "ass"),
    )
