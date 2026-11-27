from typing import Literal

from pydantic import BaseModel, Field

from .common import ExtractionProvenance, SourceEvidence

EntityType = Literal["person", "place", "organization", "object", "animal", "group", "other"]
MentionKind = Literal["proper_name", "nominal_reference", "pronoun", "description", "unknown"]


class EntityCandidate(BaseModel):
    """Untrusted semantic fields returned by the model; no IDs or offsets are accepted."""
    segment_id: str
    surface_text: str = Field(min_length=1)
    entity_type: EntityType
    mention_kind: MentionKind
    normalized_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class EntityCandidateResponse(BaseModel):
    mentions: list[EntityCandidate] = Field(default_factory=list)


class EntityMention(BaseModel):
    mention_id: str
    document_id: str
    chunk_id: str
    surface_text: str
    normalized_text: str | None = None
    entity_type: EntityType
    mention_kind: MentionKind = "unknown"
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    source_evidence: list[SourceEvidence] = Field(min_length=1)
    provenance: ExtractionProvenance


class EntityExtractionResponse(BaseModel):
    records: list[EntityMention] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
