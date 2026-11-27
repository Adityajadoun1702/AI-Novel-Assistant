import hashlib
import json
from pathlib import Path

from ..schemas.common import ExtractionProvenance, SourceEvidence
from ..schemas.entity import (
    EntityCandidateResponse,
    EntityExtractionResponse,
    EntityMention,
)


class EntityExtractor:
    """LLM identifies mention semantics; Python resolves IDs and source offsets."""

    task = "entity"
    prompt_version = "entity_v3"

    def __init__(self, llm, prompt_dir=None):
        self.llm = llm
        self.prompt_path = (
            Path(prompt_dir) / "entity.md" if prompt_dir
            else Path(__file__).parents[1] / "prompts" / "entity.md"
        )

    def extract(
        self,
        *,
        chunk,
        segments,
        document_id: str,
        normalized_text: str,
        run_id: str,
        extraction_version: int,
        candidate_hints: list[dict] | None = None,
    ) -> EntityExtractionResponse:
        prompt = self.prompt_path.read_text(encoding="utf-8")
        segment_payload = []
        segment_by_id = {}
        for segment in segments:
            sid = segment["segment_id"]
            ref = segment["source_ref"]
            start, end = ref["source_start"], ref["source_end"]
            text = normalized_text[start:end]
            if text != segment["text"]:
                raise ValueError(f"Source text mismatch for segment {sid}")
            segment_payload.append({
                "segment_id": sid,
                "text": text,
            })
            segment_by_id[sid] = segment

        user_payload = {
            "document_id": document_id,
            "chunk_id": chunk.chunk_id,
            "segments": segment_payload,
            "candidate_hints": candidate_hints or [],
            "instructions": (
                "Return one classification for each distinct (segment_id, exact surface_text, "
                "entity_type) found. Do not return offsets or occurrence indices. Python will "
                "find every exact occurrence of each surface_text in its segment."
            ),
        }
        candidate_response = self.llm.generate_structured(
            system_prompt=prompt,
            user_prompt=json.dumps(user_payload, ensure_ascii=False),
            response_schema=EntityCandidateResponse,
            temperature=0.0,
        )
        if not isinstance(candidate_response, EntityCandidateResponse):
            candidate_response = EntityCandidateResponse.model_validate(candidate_response)

        records = []
        warnings = []
        seen = set()
        for candidate in candidate_response.mentions:
            segment = segment_by_id.get(candidate.segment_id)
            if segment is None:
                warnings.append(
                    f"Skipped mention {candidate.surface_text!r}: model returned unknown "
                    f"segment {candidate.segment_id!r}"
                )
                continue
            segment_text = segment["text"]
            positions = []
            cursor = 0
            while True:
                found = segment_text.find(candidate.surface_text, cursor)
                if found < 0:
                    break
                positions.append(found)
                cursor = found + len(candidate.surface_text)
            if not positions:
                warnings.append(
                    f"Skipped mention {candidate.surface_text!r}: exact text was not found "
                    f"in segment {candidate.segment_id}"
                )
                continue
            for position in positions:
                ref = segment["source_ref"]
                start = ref["source_start"] + position
                end = start + len(candidate.surface_text)
                if normalized_text[start:end] != candidate.surface_text:
                    raise ValueError("Resolved mention does not match normalized source")
                paragraph_id = segment["paragraph_id"]
                dedupe_key = (candidate.segment_id, start, end, candidate.entity_type)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                stable_key = (
                    f"{document_id}|{chunk.chunk_id}|{candidate.segment_id}|"
                    f"{start}|{end}|{candidate.entity_type}"
                )
                mention_id = "MENTION_" + hashlib.sha256(
                    stable_key.encode("utf-8")
                ).hexdigest()[:16].upper()

                evidence = SourceEvidence(
                    document_id=document_id,
                    chunk_id=chunk.chunk_id,
                    paragraph_ids=[paragraph_id],
                    segment_ids=[candidate.segment_id],
                    start_offset=start,
                    end_offset=end,
                    exact_text=candidate.surface_text,
                )
                provenance = ExtractionProvenance(
                    method="hybrid",
                    provider=getattr(self.llm, "provider", "unknown"),
                    model=getattr(self.llm, "model", "unknown"),
                    prompt_version=self.prompt_version,
                    extraction_version=str(extraction_version),
                    extraction_run_id=run_id,
                    confidence=candidate.confidence,
                )
                records.append(EntityMention(
                    mention_id=mention_id,
                    document_id=document_id,
                    chunk_id=chunk.chunk_id,
                    surface_text=candidate.surface_text,
                    normalized_text=candidate.normalized_text or candidate.surface_text,
                    entity_type=candidate.entity_type,
                    mention_kind=candidate.mention_kind,
                    source_evidence=[evidence],
                    provenance=provenance,
                ))

        records.sort(key=lambda item: (
            item.source_evidence[0].start_offset,
            item.source_evidence[0].end_offset,
            item.mention_id,
        ))
        return EntityExtractionResponse(records=records, warnings=warnings)
