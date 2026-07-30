import re
from pathlib import Path
from typing import Iterable

_model_cache = {}


def srt_timestamp(seconds: float) -> str:
    ms = max(0, round(float(seconds) * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_srt(entries: Iterable[dict], destination: Path) -> None:
    blocks = []
    index = 1
    for item in entries:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        blocks.append(f"{index}\n{srt_timestamp(item['start'])} --> {srt_timestamp(item['end'])}\n{text}\n")
        index += 1
    destination.write_text("\n".join(blocks), encoding="utf-8")


def _script_chunks(script: str, max_words: int = 10) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n+", script) if p.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
        for sentence in sentences:
            words = sentence.split()
            while len(words) > max_words:
                chunks.append(" ".join(words[:max_words]))
                words = words[max_words:]
            if words:
                chunks.append(" ".join(words))
    return chunks


def align_script_to_timing(script: str, whisper_segments: list[dict]) -> list[dict]:
    chunks = _script_chunks(script)
    if not chunks:
        return whisper_segments
    start = float(whisper_segments[0].get("start", 0.0))
    end = float(whisper_segments[-1].get("end", start + 1.0))
    total_duration = max(0.1, end - start)
    weights = [max(1, len(chunk.split())) for chunk in chunks]
    total_weight = sum(weights)
    cursor = start
    aligned = []
    for i, (chunk, weight) in enumerate(zip(chunks, weights)):
        duration = total_duration * weight / total_weight
        chunk_end = end if i == len(chunks) - 1 else cursor + duration
        aligned.append({"start": cursor, "end": chunk_end, "text": chunk})
        cursor = chunk_end
    return aligned


def generate_captions(narration: Path, destination: Path, script: str = "", model_name: str = "base") -> str:
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("Whisper is not installed. Launch the app with Start Mother Earth Studio.command.") from exc
    model = _model_cache.get(model_name)
    if model is None:
        model = whisper.load_model(model_name)
        _model_cache[model_name] = model
    result = model.transcribe(str(narration), fp16=False, verbose=False)
    segments = result.get("segments") or []
    if not segments:
        raise RuntimeError("Whisper did not return any caption segments.")
    entries = align_script_to_timing(script, segments) if script.strip() else segments
    write_srt(entries, destination)
    return str(result.get("language", ""))
