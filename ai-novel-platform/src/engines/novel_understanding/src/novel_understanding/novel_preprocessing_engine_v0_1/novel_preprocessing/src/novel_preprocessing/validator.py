from __future__ import annotations

from .schemas import (
    Segment,
    ParagraphAnnotation,
    DialogueCandidate,
    ContextChunk,
)


def validate_preprocessing(
    paragraphs: list[dict],
    segments: list[Segment],
    annotations: list[ParagraphAnnotation],
    dialogue_candidates: list[DialogueCandidate],
    chunks: list[ContextChunk],
) -> list[str]:
    errors: list[str] = []
    paragraph_by_id: dict[str, dict] = {}

    for paragraph in paragraphs:
        pid = str(paragraph.get("paragraph_id", paragraph.get("id", "")))
        if not pid:
            errors.append("A paragraph is missing paragraph_id/id")
            continue
        if pid in paragraph_by_id:
            errors.append(f"Duplicate paragraph ID: {pid}")
        paragraph_by_id[pid] = paragraph

    segment_ids: set[str] = set()
    segment_by_id: dict[str, Segment] = {}
    by_para: dict[str, list[Segment]] = {}

    for segment in segments:
        if segment.segment_id in segment_ids:
            errors.append(f"Duplicate segment ID: {segment.segment_id}")
        segment_ids.add(segment.segment_id)
        segment_by_id[segment.segment_id] = segment

        if segment.paragraph_id not in paragraph_by_id:
            errors.append(
                f"Segment {segment.segment_id} references unknown paragraph "
                f"{segment.paragraph_id}"
            )
            continue

        if segment.source_ref.local_end < segment.source_ref.local_start:
            errors.append(f"Invalid local range in {segment.segment_id}")

        if (
            segment.source_ref.source_start is not None
            and segment.source_ref.source_end is not None
            and segment.source_ref.source_end < segment.source_ref.source_start
        ):
            errors.append(f"Invalid source range in {segment.segment_id}")

        by_para.setdefault(segment.paragraph_id, []).append(segment)

    for pid, items in by_para.items():
        source_text = str(paragraph_by_id[pid].get("text", ""))
        ordered = sorted(items, key=lambda item: item.sequence)

        for expected, item in enumerate(ordered):
            if item.sequence != expected:
                errors.append(f"Non-contiguous segment sequence in paragraph {pid}")
            if item.source_ref.local_end > len(source_text):
                errors.append(f"Segment {item.segment_id} exceeds paragraph text length")
                continue
            actual = source_text[
                item.source_ref.local_start:item.source_ref.local_end
            ]
            if item.text != actual:
                errors.append(
                    f"Segment {item.segment_id} text does not match source slice"
                )

    for annotation in annotations:
        if annotation.paragraph_id not in paragraph_by_id:
            errors.append(
                f"Annotation references unknown paragraph {annotation.paragraph_id}"
            )
        for segment_id in annotation.segment_ids:
            if segment_id not in segment_ids:
                errors.append(
                    f"Annotation references unknown segment {segment_id}"
                )

    for candidate in dialogue_candidates:
        if candidate.paragraph_id not in paragraph_by_id:
            errors.append(
                f"Dialogue candidate references unknown paragraph {candidate.paragraph_id}"
            )
            continue

        if not candidate.segment_ids:
            errors.append(
                f"Dialogue candidate {candidate.candidate_id} has no linked segments"
            )
            continue

        linked = []
        for segment_id in candidate.segment_ids:
            segment = segment_by_id.get(segment_id)
            if segment is None:
                errors.append(
                    f"Dialogue candidate {candidate.candidate_id} references "
                    f"unknown segment {segment_id}"
                )
            else:
                if segment.paragraph_id != candidate.paragraph_id:
                    errors.append(
                        f"Dialogue candidate {candidate.candidate_id} links a "
                        "segment from another paragraph"
                    )
                linked.append(segment)

        source_text = str(paragraph_by_id[candidate.paragraph_id].get("text", ""))
        start = candidate.source_ref.local_start
        end = candidate.source_ref.local_end
        if end > len(source_text) or end < start:
            errors.append(
                f"Dialogue candidate {candidate.candidate_id} has invalid source range"
            )
        elif source_text[start:end] != candidate.text:
            errors.append(
                f"Dialogue candidate {candidate.candidate_id} text does not match source slice"
            )

        if linked:
            quote_start = candidate.source_ref.local_start
            quote_end = candidate.source_ref.local_end
            if not any(
                item.source_ref.local_start < quote_end
                and item.source_ref.local_end > quote_start
                for item in linked
            ):
                errors.append(
                    f"Dialogue candidate {candidate.candidate_id} has no overlapping linked segment"
                )

    chunk_ids: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in chunk_ids:
            errors.append(f"Duplicate chunk ID: {chunk.chunk_id}")
        chunk_ids.add(chunk.chunk_id)
        for source in chunk.source_map:
            if source.paragraph_id not in paragraph_by_id:
                errors.append(
                    f"Chunk {chunk.chunk_id} references unknown paragraph {source.paragraph_id}"
                )
            for segment_id in source.segment_ids:
                if segment_id not in segment_ids:
                    errors.append(
                        f"Chunk {chunk.chunk_id} references unknown segment {segment_id}"
                    )

    return errors
