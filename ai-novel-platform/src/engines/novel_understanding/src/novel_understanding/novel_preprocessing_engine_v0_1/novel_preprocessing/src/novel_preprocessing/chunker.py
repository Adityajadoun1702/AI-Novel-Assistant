from __future__ import annotations

from dataclasses import dataclass
from .schemas import ContextChunk, ChunkSource, Segment


@dataclass
class _Unit:
    paragraph_id: str
    chapter_id: str | None
    text: str
    segment_ids: list[str]
    source_start: int | None
    source_end: int | None


def estimate_tokens(text: str) -> int:
    # Deliberately approximate and provider-independent.
    return max(1, (len(text) + 3) // 4) if text else 0


def build_chunks(
    paragraph_records: list[dict],
    segments: list[Segment],
    max_tokens: int = 700,
    overlap_segments: int = 1,
) -> list[ContextChunk]:
    if max_tokens < 32:
        raise ValueError("max_tokens must be at least 32")
    if overlap_segments < 0:
        raise ValueError("overlap_segments cannot be negative")

    seg_by_para: dict[str, list[Segment]] = {}
    for seg in segments:
        seg_by_para.setdefault(seg.paragraph_id, []).append(seg)

    units: list[_Unit] = []
    for para in paragraph_records:
        pid = _paragraph_id(para)
        text = str(para.get("text", ""))
        psegments = seg_by_para.get(pid, [])
        if not psegments and text.strip():
            continue
        chapter_id = para.get("chapter_id")
        for seg in psegments:
            units.append(_Unit(
                paragraph_id=pid,
                chapter_id=chapter_id,
                text=seg.text,
                segment_ids=[seg.segment_id],
                source_start=seg.source_ref.source_start,
                source_end=seg.source_ref.source_end,
            ))

    grouped: list[list[_Unit]] = []
    current: list[_Unit] = []
    current_tokens = 0
    current_chapter = None

    for unit in units:
        cost = estimate_tokens(unit.text)
        chapter_break = current and unit.chapter_id != current_chapter
        if current and (current_tokens + cost > max_tokens or chapter_break):
            grouped.append(current)
            carry = current[-overlap_segments:] if overlap_segments else []
            current = list(carry)
            current_tokens = sum(estimate_tokens(x.text) for x in current)
        if cost > max_tokens and not current:
            # Keep an oversized sentence intact rather than destroying provenance.
            grouped.append([unit])
            current = []
            current_tokens = 0
            current_chapter = unit.chapter_id
            continue
        current.append(unit)
        current_tokens += cost
        current_chapter = unit.chapter_id

    if current:
        grouped.append(current)

    chunks: list[ContextChunk] = []
    for idx, group in enumerate(grouped):
        text = "\n".join(unit.text for unit in group)
        source_map: list[ChunkSource] = []
        seen: set[str] = set()
        for unit in group:
            if unit.paragraph_id not in seen:
                related = [x for x in group if x.paragraph_id == unit.paragraph_id]
                starts = [x.source_start for x in related if x.source_start is not None]
                ends = [x.source_end for x in related if x.source_end is not None]
                source_map.append(ChunkSource(
                    paragraph_id=unit.paragraph_id,
                    segment_ids=[sid for x in related for sid in x.segment_ids],
                    source_start=min(starts) if starts else None,
                    source_end=max(ends) if ends else None,
                ))
                seen.add(unit.paragraph_id)
        chapters = {u.chapter_id for u in group}
        chunk = ContextChunk(
            chunk_id=f"CHK_{idx + 1:06d}",
            sequence=idx,
            chapter_id=next(iter(chapters)) if len(chapters) == 1 else None,
            text=text,
            estimated_tokens=estimate_tokens(text),
            source_map=source_map,
        )
        chunks.append(chunk)

    for idx, chunk in enumerate(chunks):
        chunk.previous_chunk_id = chunks[idx - 1].chunk_id if idx > 0 else None
        chunk.next_chunk_id = chunks[idx + 1].chunk_id if idx + 1 < len(chunks) else None
    return chunks


def _paragraph_id(record: dict) -> str:
    value = record.get("paragraph_id", record.get("id"))
    if not value:
        raise ValueError("Paragraph record is missing paragraph_id/id")
    return str(value)
