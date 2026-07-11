"""Section-aware chunking of parsed PDF items.

Groups ParsedItems into chunks:
- Table items always become their own chunk, verbatim, never split,
  regardless of size (a partial table is retrieval-useless).
- Non-table items are grouped by their section_number in document order
  and split into ~500-800 token pieces with ~15% overlap only if a
  section's combined text exceeds that range.
- If no section headings were detected at all (parse.py's fallback case,
  section_number is None for every item), falls back to fixed-size
  ~500-800 token windows with ~15% overlap across the whole document's
  body text instead of per-section grouping. Tables still stay whole and
  separate even in this fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from ingestion.parse import ParsedItem

TARGET_MAX_TOKENS = 800
OVERLAP_RATIO = 0.15

_encoding = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    text: str
    page_no: int | None
    section_number: str | None
    content_type: str


def _split_with_overlap(
    text: str, page_no: int | None, section_number: str | None, content_type: str
) -> list[Chunk]:
    """Split a long text into ~800-token windows with ~15% overlap."""
    tokens = _encoding.encode(text)
    if len(tokens) <= TARGET_MAX_TOKENS:
        return [Chunk(text=text, page_no=page_no, section_number=section_number, content_type=content_type)]

    overlap = int(TARGET_MAX_TOKENS * OVERLAP_RATIO)
    step = TARGET_MAX_TOKENS - overlap
    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + TARGET_MAX_TOKENS, len(tokens))
        window_text = _encoding.decode(tokens[start:end])
        chunks.append(
            Chunk(text=window_text, page_no=page_no, section_number=section_number, content_type=content_type)
        )
        if end == len(tokens):
            break
        start += step
    return chunks


def chunk_items(items: list[ParsedItem]) -> list[Chunk]:
    chunks: list[Chunk] = []
    has_sections = any(item.section_number is not None for item in items)

    if not has_sections:
        body_items = [i for i in items if i.content_type != "table"]
        table_items = [i for i in items if i.content_type == "table"]

        combined = "\n\n".join(i.text for i in body_items)
        if combined:
            first_page = body_items[0].page_no if body_items else None
            chunks.extend(_split_with_overlap(combined, first_page, None, body_items[0].content_type))
        for t in table_items:
            chunks.append(Chunk(text=t.text, page_no=t.page_no, section_number=None, content_type="table"))
        return chunks

    def flush(buffer: list[ParsedItem]) -> None:
        if not buffer:
            return
        combined_text = "\n\n".join(b.text for b in buffer)
        chunks.extend(
            _split_with_overlap(
                combined_text, buffer[0].page_no, buffer[0].section_number, buffer[0].content_type
            )
        )

    buffer: list[ParsedItem] = []
    current_key: tuple[str | None, str] | None = None

    for item in items:
        if item.content_type == "table":
            flush(buffer)
            buffer = []
            current_key = None
            chunks.append(
                Chunk(text=item.text, page_no=item.page_no, section_number=item.section_number, content_type="table")
            )
            continue

        key = (item.section_number, item.content_type)
        if current_key is not None and key != current_key:
            flush(buffer)
            buffer = []
        buffer.append(item)
        current_key = key

    flush(buffer)
    return chunks
