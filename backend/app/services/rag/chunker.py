"""Markdown text chunker for RAG ingestion — Sprint 2.

Splits body_markdown into overlapping token-bounded chunks using tiktoken.
Falls back to character-based splitting if tiktoken is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

log = structlog.get_logger()

_CHUNK_TOKENS = 800
_OVERLAP_TOKENS = 100


@dataclass
class TextChunk:
    position: int
    section_path: str | None
    text: str
    token_count: int


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base (openai default)."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4  # ~4 chars per token fallback


def _split_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Split text into token-bounded chunks with overlap."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(text)
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunks.append(enc.decode(chunk_tokens))
            if end == len(tokens):
                break
            start = end - overlap_tokens
        return chunks
    except Exception:
        # Character-based fallback: ~4 chars per token
        max_chars = max_tokens * 4
        overlap_chars = overlap_tokens * 4
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - overlap_chars
        return chunks


def _extract_section(line: str) -> str | None:
    """Extract heading text from a markdown heading line."""
    if line.startswith("#"):
        return line.lstrip("#").strip()
    return None


def chunk_markdown(body_markdown: str) -> list[TextChunk]:
    """Split markdown into chunks preserving section context.

    Splits at paragraph boundaries when possible. Heading lines are tracked
    as section_path for citation context in retrieval.
    """
    if not body_markdown.strip():
        return []

    paragraphs: list[tuple[str | None, str]] = []  # (section, text)
    current_section: str | None = None
    current_paras: list[str] = []

    for line in body_markdown.splitlines(keepends=True):
        stripped = line.rstrip()
        heading = _extract_section(stripped) if stripped.startswith("#") else None
        if heading:
            if current_paras:
                paragraphs.append((current_section, "".join(current_paras).strip()))
                current_paras = []
            current_section = heading
        else:
            current_paras.append(line)

    if current_paras:
        paragraphs.append((current_section, "".join(current_paras).strip()))

    # Group paragraphs into chunks of max _CHUNK_TOKENS with _OVERLAP_TOKENS overlap
    chunks: list[TextChunk] = []
    position = 0
    accumulated = ""
    accumulated_section: str | None = None
    accumulated_tokens = 0

    for section, para_text in paragraphs:
        if not para_text.strip():
            continue
        para_tokens = _count_tokens(para_text)

        if accumulated_tokens + para_tokens > _CHUNK_TOKENS and accumulated:
            # Flush current chunk
            for sub in _split_by_tokens(accumulated, _CHUNK_TOKENS, _OVERLAP_TOKENS):
                if sub.strip():
                    chunks.append(
                        TextChunk(
                            position=position,
                            section_path=accumulated_section,
                            text=sub.strip(),
                            token_count=_count_tokens(sub),
                        )
                    )
                    position += 1
            # Start new chunk with overlap from end of current accumulated
            overlap_text = (
                accumulated[-_OVERLAP_TOKENS * 4 :]
                if len(accumulated) > _OVERLAP_TOKENS * 4
                else accumulated
            )
            accumulated = overlap_text + "\n\n" + para_text
            accumulated_section = section or accumulated_section
            accumulated_tokens = _count_tokens(accumulated)
        else:
            if accumulated:
                accumulated += "\n\n" + para_text
            else:
                accumulated = para_text
                accumulated_section = section
            accumulated_tokens += para_tokens

    if accumulated.strip():
        for sub in _split_by_tokens(accumulated, _CHUNK_TOKENS, _OVERLAP_TOKENS):
            if sub.strip():
                chunks.append(
                    TextChunk(
                        position=position,
                        section_path=accumulated_section,
                        text=sub.strip(),
                        token_count=_count_tokens(sub),
                    )
                )
                position += 1

    log.debug("chunker.done", total_chunks=len(chunks))
    return chunks
