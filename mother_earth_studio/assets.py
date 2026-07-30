from pathlib import Path
from .paths import FOREST_DIR, NARRATION_DIR, MUSIC_DIR, SUBTITLES_DIR, SCRIPTS_DIR

ASSET_DIRS = {
    "forest": FOREST_DIR,
    "narration": NARRATION_DIR,
    "music": MUSIC_DIR,
    "subtitles": SUBTITLES_DIR,
    "scripts": SCRIPTS_DIR,
}


def newest_file(folder: Path, patterns: tuple[str, ...]) -> Path | None:
    files = [p for pattern in patterns for p in folder.glob(pattern) if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None
