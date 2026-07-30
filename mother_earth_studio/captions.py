import re
from pathlib import Path
from typing import Iterable

_model_cache = {}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "but", "by", "can", "could",
    "did", "do", "does", "every", "for", "from", "had", "has", "have", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just", "me", "maybe", "more",
    "my", "not", "of", "on", "only", "or", "our", "ours", "she", "should", "so", "something", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this", "those", "to", "today",
    "too", "ultimately", "us", "was", "we", "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "would", "you", "your"
}


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


def _clean_word(word: str) -> str:
    return re.sub(r"(^[^\w']+|[^\w'.!?-]+$)", "", word, flags=re.UNICODE)


def _important_phrase(text: str, max_words: int = 5) -> str:
    original = [_clean_word(w) for w in text.split()]
    original = [w for w in original if w]
    if not original:
        return ""

    # Preserve intentionally short spoken beats such as "Water. Energy. Land."
    if len(original) <= max_words:
        return " ".join(original)

    scored = []
    for index, word in enumerate(original):
        plain = re.sub(r"[^\w']", "", word).lower()
        if not plain or plain in STOP_WORDS:
            continue
        score = 1.0
        score += min(len(plain), 12) / 12
        if word[:1].isupper() and index > 0:
            score += 0.35
        if any(mark in word for mark in "?!"):
            score += 0.45
        scored.append((score, index, word))

    if not scored:
        return " ".join(original[:max_words])

    chosen_indices = sorted(index for _, index, _ in sorted(scored, reverse=True)[:max_words])
    phrase = " ".join(original[index] for index in chosen_indices)
    return phrase.strip()


def story_first_entries(entries: list[dict], max_words: int = 5, min_gap: float = 0.12) -> list[dict]:
    """Convert transcript-like cues into concise, cinematic emphasis phrases."""
    story: list[dict] = []
    previous = ""
    for item in entries:
        phrase = _important_phrase(str(item.get("text", "")), max_words=max_words)
        if not phrase or phrase.lower() == previous.lower():
            continue
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start + 1.5))
        duration = max(1.15, min(3.8, end - start))
        end = start + duration
        if story and start < story[-1]["end"] + min_gap:
            start = story[-1]["end"] + min_gap
            end = max(start + 1.15, end)
        story.append({"start": start, "end": end, "text": phrase})
        previous = phrase
    return story


def generate_captions(narration: Path, destination: Path, script: str = "", model_name: str = "base",
                      story_first: bool = True) -> str:
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
    if story_first:
        entries = story_first_entries(entries)
    write_srt(entries, destination)
    return str(result.get("language", ""))
