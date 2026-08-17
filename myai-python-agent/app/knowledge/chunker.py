from dataclasses import dataclass
from typing import List


@dataclass
class TextChunk:
    content: str
    char_start: int
    char_end: int
    token_estimate: int


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    return [chunk.content for chunk in chunk_text_with_spans(text, chunk_size=chunk_size, overlap=overlap)]


def chunk_text_with_spans(text: str, chunk_size: int = 700, overlap: int = 100) -> List[TextChunk]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    if not paragraphs:
        return [_make_chunk(normalized, normalized, 0)]

    chunks: List[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = _with_overlap(current, overlap, paragraph)
            if len(current) > chunk_size:
                chunks.extend(_split_long_text(current, chunk_size, overlap))
                current = ""
        else:
            chunks.extend(_split_long_text(paragraph, chunk_size, overlap))

    if current:
        chunks.append(current)

    return _attach_spans(normalized, [chunk.strip() for chunk in chunks if chunk.strip()])


def _split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    pieces: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return pieces


def _with_overlap(previous: str, overlap: int, next_paragraph: str) -> str:
    tail = previous[-overlap:].strip() if overlap > 0 else ""
    if tail:
        return f"{tail}\n\n{next_paragraph}"
    return next_paragraph


def _attach_spans(normalized: str, chunks: List[str]) -> List[TextChunk]:
    attached: List[TextChunk] = []
    cursor = 0
    for chunk in chunks:
        start = normalized.find(chunk, cursor)
        if start == -1:
            start = normalized.find(chunk)
        if start == -1:
            start = cursor
        end = min(len(normalized), start + len(chunk))
        attached.append(_make_chunk(chunk, normalized, start, end))
        cursor = max(cursor, end)
    return attached


def _make_chunk(content: str, normalized: str, start: int, end: int | None = None) -> TextChunk:
    end = len(normalized) if end is None else end
    return TextChunk(
        content=content,
        char_start=max(0, start),
        char_end=max(0, end),
        token_estimate=max(1, len(content) // 4),
    )
