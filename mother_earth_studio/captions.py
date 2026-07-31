from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Iterable

_model_cache = {}

MAX_CAPTION_WORDS = 8
MAX_LINE_CHARACTERS = 28
MAX_CAPTION_LINES = 2
MIN_CAPTION_DURATION = 1.0


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(
        0,
        round(float(seconds) * 1000),
    )

    hours, remainder = divmod(
        milliseconds,
        3_600_000,
    )

    minutes, remainder = divmod(
        remainder,
        60_000,
    )

    seconds_value, milliseconds = divmod(
        remainder,
        1_000,
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds_value:02d},"
        f"{milliseconds:03d}"
    )


def normalize_caption_text(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", str(text))
    cleaned = cleaned.replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def wrap_caption_text(
    text: str,
    width: int = MAX_LINE_CHARACTERS,
) -> str:
    cleaned = normalize_caption_text(text)

    if not cleaned:
        return ""

    lines = textwrap.wrap(
        cleaned,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )

    return "\n".join(lines)


def _split_long_sentence(
    sentence: str,
    max_words: int = MAX_CAPTION_WORDS,
    max_characters: int = MAX_LINE_CHARACTERS * MAX_CAPTION_LINES,
) -> list[str]:
    words = sentence.split()

    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []

    for word in words:
        candidate_words = [*current, word]
        candidate = " ".join(candidate_words)

        exceeds_words = len(candidate_words) > max_words
        exceeds_characters = len(candidate) > max_characters

        if current and (
            exceeds_words
            or exceeds_characters
        ):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current = candidate_words

    if current:
        chunks.append(" ".join(current))

    return chunks


def caption_chunks(
    text: str,
    max_words: int = MAX_CAPTION_WORDS,
) -> list[str]:
    cleaned = normalize_caption_text(text)

    if not cleaned:
        return []

    sentence_parts = re.split(
        r"(?<=[.!?])\s+",
        cleaned,
    )

    chunks: list[str] = []

    for sentence in sentence_parts:
        sentence = sentence.strip()

        if not sentence:
            continue

        clause_parts = re.split(
            r"(?<=[,;:])\s+",
            sentence,
        )

        for clause in clause_parts:
            clause = clause.strip()

            if not clause:
                continue

            chunks.extend(
                _split_long_sentence(
                    clause,
                    max_words=max_words,
                )
            )

    return chunks


def _split_timed_entry(
    entry: dict,
) -> list[dict]:
    start = float(entry.get("start", 0.0))
    end = float(
        entry.get(
            "end",
            start + MIN_CAPTION_DURATION,
        )
    )

    chunks = caption_chunks(
        str(entry.get("text", "")),
    )

    if not chunks:
        return []

    duration = max(
        MIN_CAPTION_DURATION,
        end - start,
    )

    weights = [
        max(1, len(chunk.split()))
        for chunk in chunks
    ]

    total_weight = sum(weights)
    cursor = start
    result: list[dict] = []

    for index, (chunk, weight) in enumerate(
        zip(chunks, weights)
    ):
        chunk_duration = (
            duration * weight / total_weight
        )

        chunk_end = (
            end
            if index == len(chunks) - 1
            else cursor + chunk_duration
        )

        result.append(
            {
                "start": cursor,
                "end": max(
                    cursor + 0.25,
                    chunk_end,
                ),
                "text": chunk,
            }
        )

        cursor = chunk_end

    return result


def caption_safe_entries(
    entries: Iterable[dict],
) -> list[dict]:
    safe_entries: list[dict] = []

    for entry in entries:
        safe_entries.extend(
            _split_timed_entry(entry)
        )

    return safe_entries


def write_srt(
    entries: Iterable[dict],
    destination: Path,
) -> None:
    blocks: list[str] = []
    index = 1

    for item in entries:
        text = wrap_caption_text(
            str(item.get("text", ""))
        )

        if not text:
            continue

        lines = text.splitlines()

        if len(lines) > MAX_CAPTION_LINES:
            raise RuntimeError(
                "Caption safety check failed: "
                f"cue {index} exceeds "
                f"{MAX_CAPTION_LINES} lines."
            )

        start = float(item["start"])
        end = float(item["end"])

        if end <= start:
            continue

        blocks.append(
            f"{index}\n"
            f"{srt_timestamp(start)} --> "
            f"{srt_timestamp(end)}\n"
            f"{text}\n"
        )

        index += 1

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        "\n".join(blocks),
        encoding="utf-8",
    )


def align_script_to_timing(
    script: str,
    whisper_segments: list[dict],
) -> list[dict]:
    chunks = caption_chunks(script)

    if not chunks:
        return caption_safe_entries(
            whisper_segments
        )

    start = float(
        whisper_segments[0].get(
            "start",
            0.0,
        )
    )

    end = float(
        whisper_segments[-1].get(
            "end",
            start + 1.0,
        )
    )

    total_duration = max(
        0.1,
        end - start,
    )

    weights = [
        max(1, len(chunk.split()))
        for chunk in chunks
    ]

    total_weight = sum(weights)
    cursor = start
    aligned: list[dict] = []

    for index, (chunk, weight) in enumerate(
        zip(chunks, weights)
    ):
        duration = (
            total_duration * weight / total_weight
        )

        chunk_end = (
            end
            if index == len(chunks) - 1
            else cursor + duration
        )

        aligned.append(
            {
                "start": cursor,
                "end": chunk_end,
                "text": chunk,
            }
        )

        cursor = chunk_end

    return aligned


def story_first_entries(
    entries: list[dict],
    max_words: int = MAX_CAPTION_WORDS,
    min_gap: float = 0.06,
) -> list[dict]:
    """
    Preserve the complete spoken wording while formatting it
    into short, readable, story-first caption cues.

    This function deliberately does not summarize, score,
    remove stop words, or select keywords.
    """
    del max_words

    safe_entries = caption_safe_entries(
        entries
    )

    adjusted: list[dict] = []

    for entry in safe_entries:
        start = float(entry["start"])
        end = float(entry["end"])

        if adjusted:
            previous_end = float(
                adjusted[-1]["end"]
            )

            if start < previous_end + min_gap:
                start = previous_end + min_gap

        if end <= start:
            end = start + MIN_CAPTION_DURATION

        adjusted.append(
            {
                "start": start,
                "end": end,
                "text": entry["text"],
            }
        )

    return adjusted


def generate_captions(
    narration: Path,
    destination: Path,
    script: str = "",
    model_name: str = "base",
    story_first: bool = True,
) -> str:
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "Whisper is not installed. "
            "Launch the app with "
            "Start Mother Earth Studio.command."
        ) from exc

    model = _model_cache.get(model_name)

    if model is None:
        model = whisper.load_model(model_name)
        _model_cache[model_name] = model

    result = model.transcribe(
        str(narration),
        fp16=False,
        verbose=False,
    )

    segments = result.get("segments") or []

    if not segments:
        raise RuntimeError(
            "Whisper did not return any "
            "caption segments."
        )

    if script.strip():
        entries = align_script_to_timing(
            script,
            segments,
        )
    else:
        entries = caption_safe_entries(
            segments
        )

    if story_first:
        entries = story_first_entries(
            entries
        )

    write_srt(
        entries,
        destination,
    )

    return str(
        result.get("language", "")
    )
