from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timezone

from .io import read_json, unwrap_records, write_json
from .segmenter import split_sentences
from .classifier import classify_paragraph, classify_segment
from .quote_detector import find_quoted_spans
from .schemas import SourceRef, Segment, ParagraphAnnotation, DialogueCandidate
from .chunker import build_chunks
from .validator import validate_preprocessing


class PreprocessingPipeline:
    def __init__(self, max_chunk_tokens: int = 700, overlap_segments: int = 1):
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_segments = overlap_segments

    def run(
        self,
        ingestion_dir: str | Path,
        output_dir: str | Path | None = None,
        document_id: str | None = None,
        version: int = 1,
    ) -> dict:
        ingestion_dir = Path(ingestion_dir).resolve()

        # Expected input: processed/DOC_ID/ingestion_vN/
        # Default output root: processed/
        if output_dir is None:
            output_dir = ingestion_dir.parent.parent
        else:
            output_dir = Path(output_dir).resolve()

        paragraphs = unwrap_records(
            read_json(ingestion_dir / "paragraphs.json"), "paragraphs"
        )
        metadata_path = ingestion_dir / "metadata.json"
        metadata = read_json(metadata_path) if metadata_path.exists() else {}
        document_id = (
            document_id
            or str(metadata.get("document_id") or metadata.get("doc_id") or ingestion_dir.parent.name)
        )

        normalized_path = ingestion_dir / "normalized.txt"
        normalized_text = (
            normalized_path.read_text(encoding="utf-8")
            if normalized_path.exists()
            else None
        )
        normalized_hash = (
            hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
            if normalized_text is not None
            else None
        )

        heading_candidate_offsets: set[tuple[int, int]] = set()
        heading_candidates_path = ingestion_dir / "heading_candidates.json"
        if heading_candidates_path.exists():
            raw_candidates = unwrap_records(
                read_json(heading_candidates_path), "heading_candidates"
            )
            for candidate in raw_candidates:
                start = candidate.get("start_offset")
                end = candidate.get("end_offset")
                if start is not None and end is not None:
                    heading_candidate_offsets.add((int(start), int(end)))

        structure_path = ingestion_dir / "structure_analysis.json"
        structure_status = None
        if structure_path.exists():
            structure_data = read_json(structure_path)
            structure_status = structure_data.get("status")

        segments: list[Segment] = []
        annotations: list[ParagraphAnnotation] = []
        dialogue_candidates: list[DialogueCandidate] = []

        for p_index, paragraph in enumerate(paragraphs):
            pid = str(
                paragraph.get("paragraph_id", paragraph.get("id", f"P_{p_index + 1:06d}"))
            )
            text = str(paragraph.get("text", ""))
            if not text.strip():
                continue

            base_offset = paragraph.get("start_offset", paragraph.get("source_start"))
            base_offset = int(base_offset) if base_offset is not None else None
            chapter_id = paragraph.get("chapter_id")

            is_confirmed_heading = (
                paragraph.get("paragraph_type") == "chapter_heading"
                or paragraph.get("is_heading") is True
            )
            is_heading_candidate = (
                paragraph.get("is_heading_candidate") is True
                or (
                    base_offset is not None
                    and (base_offset, base_offset + len(text)) in heading_candidate_offsets
                )
            )

            p_class = classify_paragraph(
                text,
                is_heading=is_confirmed_heading,
                is_heading_candidate=is_heading_candidate,
            )
            paragraph_segment_ids: list[str] = []

            spans = split_sentences(text)
            quote_spans = find_quoted_spans(text)
            paragraph_segments: list[Segment] = []

            for s_index, span in enumerate(spans):
                # A segment is dialogue only when its entire text is inside a quote.
                # A mixed narration + quoted-speech segment remains separately annotated
                # as narration; the exact quote is represented by DialogueCandidate.
                contained_in_quote = any(
                    quote.start <= span.start and quote.end >= span.end
                    for quote in quote_spans
                )
                seg_class = classify_segment(
                    span.text,
                    is_dialogue=contained_in_quote,
                )

                source_start = base_offset + span.start if base_offset is not None else None
                source_end = base_offset + span.end if base_offset is not None else None
                sid = f"SEG_{pid}_{s_index + 1:04d}"

                segment = Segment(
                    segment_id=sid,
                    paragraph_id=pid,
                    sequence=s_index,
                    segment_type=seg_class.label,
                    text=span.text,
                    source_ref=SourceRef(
                        document_id=document_id,
                        paragraph_id=pid,
                        local_start=span.start,
                        local_end=span.end,
                        source_start=source_start,
                        source_end=source_end,
                    ),
                    classification_method=seg_class.method,
                    confidence=seg_class.confidence,
                )
                segments.append(segment)
                paragraph_segments.append(segment)
                paragraph_segment_ids.append(sid)

            # Detect each quote once, then link it to every sentence segment it overlaps.
            # This preserves multi-sentence dialogue as one complete candidate.
            for q_index, quote in enumerate(quote_spans):
                linked_segments = [
                    segment
                    for segment in paragraph_segments
                    if segment.source_ref.local_start < quote.end
                    and segment.source_ref.local_end > quote.start
                ]
                if not linked_segments:
                    continue

                q_source_start = (
                    base_offset + quote.start if base_offset is not None else None
                )
                q_source_end = (
                    base_offset + quote.end if base_offset is not None else None
                )

                dialogue_candidates.append(
                    DialogueCandidate(
                        candidate_id=f"DQC_{pid}_{q_index + 1:04d}",
                        paragraph_id=pid,
                        segment_ids=[segment.segment_id for segment in linked_segments],
                        text=quote.text,
                        quote_style=quote.quote_style,
                        source_ref=SourceRef(
                            document_id=document_id,
                            paragraph_id=pid,
                            local_start=quote.start,
                            local_end=quote.end,
                            source_start=q_source_start,
                            source_end=q_source_end,
                        ),
                        confidence=0.72,
                    )
                )

            annotations.append(
                ParagraphAnnotation(
                    paragraph_id=pid,
                    paragraph_type=p_class.label,
                    chapter_id=str(chapter_id) if chapter_id is not None else None,
                    segment_ids=paragraph_segment_ids,
                    classification_method=p_class.method,
                    confidence=p_class.confidence,
                )
            )

        chunks = build_chunks(
            paragraphs, segments, self.max_chunk_tokens, self.overlap_segments
        )
        errors = validate_preprocessing(
            paragraphs, segments, annotations, dialogue_candidates, chunks
        )

        result_dir = output_dir / document_id / f"preprocessing_v{version}"
        result_dir.mkdir(parents=True, exist_ok=False)

        write_json(
            result_dir / "paragraph_annotations.json",
            [item.model_dump() for item in annotations],
        )
        write_json(
            result_dir / "sentence_segments.json",
            [item.model_dump() for item in segments],
        )
        write_json(
            result_dir / "dialogue_candidates.json",
            [item.model_dump() for item in dialogue_candidates],
        )
        write_json(
            result_dir / "chunks.json",
            [item.model_dump() for item in chunks],
        )

        report = {
            "document_id": document_id,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_paragraph_count": len(paragraphs),
            "annotated_paragraph_count": len(annotations),
            "sentence_segment_count": len(segments),
            "dialogue_candidate_count": len(dialogue_candidates),
            "chunk_count": len(chunks),
            "source_text_sha256": normalized_hash,
            "validation_passed": not errors,
            "validation_errors": errors,
            "structure_analysis_status": structure_status,
            "classification_note": (
                "Heuristic labels are provisional. Heading-candidate labels remain "
                "provisional unless confirmed by structure analysis."
            ),
            "token_estimation": (
                "Approximate character-based estimate (about 4 characters per token)."
            ),
        }
        write_json(result_dir / "preprocessing_report.json", report)
        write_json(
            result_dir / "preprocessing_metadata.json",
            {
                "document_id": document_id,
                "version": version,
                "input_directory": str(ingestion_dir),
                "source_text_sha256": normalized_hash,
                "source_text_modified": False,
                "offset_convention": (
                    "zero-based, half-open character offsets into normalized.txt"
                ),
                "engine": "novel_preprocessing",
                "engine_version": "0.2.0",
            },
        )

        return {
            "output_directory": str(result_dir),
            "report": report,
            "validation_errors": errors,
        }
