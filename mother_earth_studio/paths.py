from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_DIR / "Assets"
FOREST_DIR = ASSETS_DIR / "Forest"
NARRATION_DIR = ASSETS_DIR / "Narration"
MUSIC_DIR = ASSETS_DIR / "Music"
SUBTITLES_DIR = ASSETS_DIR / "Subtitles"
SCRIPTS_DIR = ASSETS_DIR / "Scripts"
OUTPUT_DIR = APP_DIR / "Output"
SETTINGS_FILE = APP_DIR / "settings.json"


def ensure_folders() -> None:
    for path in (FOREST_DIR, NARRATION_DIR, MUSIC_DIR, SUBTITLES_DIR, SCRIPTS_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)
