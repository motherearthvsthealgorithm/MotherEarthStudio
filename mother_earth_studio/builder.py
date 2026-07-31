import re
import shutil
import subprocess
import tempfile
import textwrap
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .captions import wrap_caption_text
from .system_check import SystemStatus


@dataclass
class BuildResult:
    output: Path
    captions_burned: bool
    caption_renderer: str = "none"
    warning: str = ""
    log_path: Path | None = None
    caption_verification: str = "not requested"


def clean_title(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", title.strip()).strip("_")
    return cleaned or "Untitled"


def next_output_path(output_dir: Path, title: str) -> tuple[int, Path]:
    highest = 0
    for path in output_dir.glob("*.mp4"):
        match = re.match(r"^(\d{3})_", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    number = highest + 1
    return number, output_dir / f"{number:03d}_{clean_title(title)}.mp4"


def probe_duration(path: Path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def _subtitle_filter(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")
    style = "FontName=Arial,FontSize=9,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginL=90,MarginR=90,MarginV=115"
    return f"subtitles=filename='{escaped}':force_style='{style}'"


def _parse_srt(
    path: Path,
) -> list[tuple[float, float, str]]:
    text = path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    ).replace("\r\n", "\n")

    blocks = re.split(
        r"\n\s*\n",
        text.strip(),
    )

    cues: list[
        tuple[float, float, str]
    ] = []

    stamp = re.compile(
        r"(?P<sh>\d{1,2}):"
        r"(?P<sm>\d{2}):"
        r"(?P<ss>\d{2})"
        r"[,.](?P<sms>\d{3})"
        r"\s*-->\s*"
        r"(?P<eh>\d{1,2}):"
        r"(?P<em>\d{2}):"
        r"(?P<es>\d{2})"
        r"[,.](?P<ems>\d{3})"
    )

    for block in blocks:
        lines = [
            line.rstrip()
            for line in block.split("\n")
        ]

        timing_index = next(
            (
                index
                for index, line
                in enumerate(lines)
                if "-->" in line
            ),
            None,
        )

        if timing_index is None:
            continue

        match = stamp.search(
            lines[timing_index]
        )

        if not match:
            continue

        values = {
            key: int(value)
            for key, value
            in match.groupdict().items()
        }

        start = (
            values["sh"] * 3600
            + values["sm"] * 60
            + values["ss"]
            + values["sms"] / 1000
        )

        end = (
            values["eh"] * 3600
            + values["em"] * 60
            + values["es"]
            + values["ems"] / 1000
        )

        caption_source = " ".join(
            line.strip()
            for line
            in lines[timing_index + 1:]
            if line.strip()
        )

        caption = wrap_caption_text(
            caption_source
        )

        if caption and end > start:
            cues.append(
                (start, end, caption)
            )

    return cues


def _escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _find_font_file() -> Path | None:
    candidates = [
        Path(
            "/System/Library/Fonts/"
            "HelveticaNeue.ttc"
        ),
        Path(
            "/System/Library/Fonts/"
            "Helvetica.ttc"
        ),
        Path(
            "/System/Library/Fonts/"
            "Supplemental/Arial.ttf"
        ),
        Path(
            "/usr/share/fonts/truetype/"
            "dejavu/DejaVuSans.ttf"
        ),
    ]
    return next((path for path in candidates if path.exists()), None)


def _sample_region_luma(video: Path, timestamp: float, x: float, y: float, w: float = 0.34, h: float = 0.16) -> float:
    """Return average grayscale luma for a normalized frame region using FFmpeg only."""
    crop = f"crop=iw*{w:.3f}:ih*{h:.3f}:iw*{x:.3f}:ih*{y:.3f},scale=16:16,format=gray"
    command = [
        "ffmpeg", "-v", "error", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video),
        "-frames:v", "1", "-vf", crop, "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, timeout=8)
        data = result.stdout
        return sum(data) / len(data) if data else 128.0
    except Exception:
        return 128.0


def _choose_caption_position(video: Path, start: float, end: float, cue_index: int, previous: str = "") -> tuple[str, str, str]:
    candidates = [
        ("upper_left", "w*0.10", "h*0.18", 0.06, 0.12),
        ("upper_right", "w-text_w-w*0.10", "h*0.18", 0.60, 0.12),
        ("middle_left", "w*0.10", "h*0.45", 0.06, 0.39),
        ("middle_right", "w-text_w-w*0.10", "h*0.45", 0.60, 0.39),
        ("lower_center", "(w-text_w)/2", "h*0.76", 0.33, 0.70),
    ]
    timestamp = (start + end) / 2
    scored = []
    for name, x_expr, y_expr, x, y in candidates:
        luma = _sample_region_luma(video, timestamp, x, y)
        repeat_penalty = 34 if name == previous else 0
        # Prefer darker breathing room for white type; add a stable tiny tie-breaker.
        tie = int(hashlib.sha1(f"{cue_index}:{name}".encode()).hexdigest()[:2], 16) / 255
        scored.append((luma + repeat_penalty + tie, name, x_expr, y_expr))
    _, name, x_expr, y_expr = min(scored)
    return name, x_expr, y_expr


def _drawtext_filter_graph(
    subtitles: Path,
    temp_dir: Path,
    video: Path,
) -> tuple[str, int]:
    """
    Render captions as one-word-at-a-time emphasis.

    Placement is selected per caption cue by sampling the
    available video regions and choosing the darkest suitable
    safe area for white text.
    """
    cues = _parse_srt(subtitles)

    if not cues:
        raise RuntimeError(
            "The selected .srt file contains "
            "no readable caption cues."
        )

    font_file = _find_font_file()

    font_option = (
        "fontfile="
        f"'{_escape_filter_path(font_file)}'"
        if font_file
        else "font='Arial'"
    )

    filters: list[str] = []
    rendered_word_count = 0
    previous_position = ""

    for cue_index, (
        cue_start,
        cue_end,
        cue_text,
    ) in enumerate(cues, start=1):
        words = cue_text.replace(
            "\n",
            " ",
        ).split()

        if not words:
            continue

        position, x_expr, y_expr = (
            _choose_caption_position(
                video,
                cue_start,
                cue_end,
                cue_index,
                previous_position,
            )
        )

        previous_position = position

        cue_duration = max(
            0.20,
            cue_end - cue_start,
        )

        word_weights = [
            max(
                1.0,
                min(
                    2.5,
                    len(
                        re.sub(
                            r"[^\\w']",
                            "",
                            word,
                        )
                    ) / 4.0,
                ),
            )
            for word in words
        ]

        total_weight = sum(word_weights)
        cursor = cue_start

        for word_index, (
            word,
            weight,
        ) in enumerate(
            zip(words, word_weights),
            start=1,
        ):
            rendered_word_count += 1

            word_duration = (
                cue_duration
                * weight
                / total_weight
            )

            word_end = (
                cue_end
                if word_index == len(words)
                else cursor + word_duration
            )

            word_file = (
                temp_dir
                / (
                    f"cue_{cue_index:04d}_"
                    f"word_{word_index:03d}.txt"
                )
            )

            word_file.write_text(
                word,
                encoding="utf-8",
            )

            path = _escape_filter_path(
                word_file
            )

            filters.append(
                "drawtext="
                f"textfile='{path}':"
                "reload=0:"
                f"{font_option}:"
                "expansion=none:"
                "fontcolor=white:"
                "fontsize=h/21:"
                "borderw=3:"
                "bordercolor=black@0.88:"
                "shadowx=2:"
                "shadowy=3:"
                "shadowcolor=black@0.70:"
                f"x={x_expr}:"
                f"y={y_expr}:"
                f"enable='between(t,"
                f"{cursor:.3f},"
                f"{word_end:.3f})'"
            )

            cursor = word_end

    if not filters:
        raise RuntimeError(
            "Caption rendering produced no "
            "readable words."
        )

    return (
        ",".join(filters),
        rendered_word_count,
    )


def _copy_sidecar(subtitles: Path, output: Path) -> Path:
    sidecar = output.with_suffix(".srt")
    shutil.copy2(subtitles, sidecar)
    return sidecar


def _write_log(output: Path, command: list[str], stderr: str, summary: str) -> Path:
    log_path = output.with_suffix(".build.log")
    safe_command = " ".join(repr(part) for part in command)
    log_path.write_text(
        f"Mother Earth Studio build log\n\n{summary}\n\nCOMMAND\n{safe_command}\n\nFFMPEG OUTPUT\n{stderr}",
        encoding="utf-8",
    )
    return log_path


def build_episode(video: Path, narration: Path, output: Path, system: SystemStatus, music: Path | None = None,
                  subtitles: Path | None = None, music_volume: int = 18, burn_captions: bool = True) -> BuildResult:
    if not system.can_build:
        raise RuntimeError("FFmpeg and FFprobe are required to build an episode.")
    if subtitles and subtitles.suffix.lower() != ".srt":
        raise RuntimeError("Captions must be a standard .srt file.")

    output.parent.mkdir(parents=True, exist_ok=True)
    narration_duration = probe_duration(narration)
    tail_duration = 1.5
    final_duration = narration_duration + tail_duration
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "verbose", "-stream_loop", "-1", "-i", str(video), "-i", str(narration)]
    if music:
        command += ["-stream_loop", "-1", "-i", str(music)]
        duration = final_duration
        fade = min(3.0, max(1.0, narration_duration / 4))
        fade_out = max(0.0, final_duration - fade)
        volume = max(0.0, min(1.0, music_volume / 100.0))
        audio_filters = (
            f"[1:a]volume=1.0[narration];"
            f"[2:a]volume={volume:.3f},afade=t=in:st=0:d={fade:.2f},"
            f"afade=t=out:st={fade_out:.2f}:d={fade:.2f}[music];"
            f"[narration][music]amix=inputs=2:duration=longest:dropout_transition=2,atrim=duration={final_duration:.3f}[audio]"
        )
        command += ["-filter_complex", audio_filters, "-map", "0:v:0", "-map", "[audio]"]
    else:
        command += ["-map", "0:v:0", "-map", "1:a:0"]

    captions_burned = False
    renderer = "none"
    warning = ""
    verification = "not requested"
    temp_context = None
    expected_marker = ""

    if subtitles:
        _copy_sidecar(subtitles, output)

    try:
        # Always attempt the portable drawtext renderer when captions are requested.
        # Some macOS FFmpeg builds do not report filter capabilities consistently,
        # even though drawtext works when invoked directly.
        if subtitles and burn_captions:
            temp_context = tempfile.TemporaryDirectory(prefix="mother_earth_captions_")
            graph, cue_count = _drawtext_filter_graph(subtitles, Path(temp_context.name), video)
            command += ["-vf", graph]
            renderer = "portable drawtext"
            expected_marker = "drawtext"
            verification = f"requested {cue_count} cue(s)"
        elif subtitles:
            warning = "MP4 created without burned captions because caption burning was turned off. The .srt was saved beside it."
            verification = "burning disabled"

        command += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{final_duration:.3f}", str(output)
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        stderr = result.stderr or ""
        filter_initialized = bool(expected_marker and expected_marker.lower() in stderr.lower())
        if result.returncode != 0:
            log_path = _write_log(output, command, stderr, "Caption build failed before completion.")
            detail = "\n".join(stderr.strip().splitlines()[-22:])
            raise RuntimeError(f"FFmpeg build failed. Build log: {log_path}\n\n{detail}")
        if expected_marker and not filter_initialized:
            log_path = _write_log(output, command, stderr, "FFmpeg completed, but the requested caption filter was not confirmed in its log.")
            output.unlink(missing_ok=True)
            raise RuntimeError(
                "Caption build failed verification: FFmpeg did not confirm that the caption filter initialized. "
                f"No captionless video was presented as successful. Build log: {log_path}"
            )
        if expected_marker:
            captions_burned = True
            verification = "caption filter initialized and output completed"
        summary = (
            f"Output: {output.name}\nRenderer: {renderer}\nCaptions burned: {captions_burned}\n"
            f"Verification: {verification}\nWarning: {warning or 'none'}"
        )
        log_path = _write_log(output, command, stderr, summary)
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    return BuildResult(
        output=output,
        captions_burned=captions_burned,
        caption_renderer=renderer,
        warning=warning,
        log_path=log_path,
        caption_verification=verification,
    )
