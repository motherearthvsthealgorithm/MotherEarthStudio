import json
from dataclasses import asdict, dataclass
from pathlib import Path
from .paths import SETTINGS_FILE

@dataclass
class Settings:
    music_volume: int = 18
    whisper_model: str = "base"
    burn_captions_when_supported: bool = True


def load_settings(path: Path = SETTINGS_FILE) -> Settings:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Settings(**{k: v for k, v in data.items() if k in Settings.__dataclass_fields__})
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return Settings()


def save_settings(settings: Settings, path: Path = SETTINGS_FILE) -> None:
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
