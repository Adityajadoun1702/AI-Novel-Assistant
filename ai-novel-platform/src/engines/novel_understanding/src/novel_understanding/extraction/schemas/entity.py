from typing import Literal
from pydantic import BaseModel, Field
from .common import SourceEvidence, ExtractionProvenance

class EntityMention(BaseModel):
    mention_id: str
    document_id: str
    chunk_id: str
    surface_text: str
    normalized_text: str | None = None
    entity_type: Literal["person", "place", "organization", "object", "animal", "group", "other"]
    mention_kind: Literal["proper_name", "nominal_reference", "pronoun", "description", "unknown"] = "unknown"
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    source_evidence: list[SourceEvidence] = Field(min_length=1)
    provenance: ExtractionProvenance

class EntityExtractionResponse(BaseModel):
    records: list[EntityMention] = Field(default_factory=list)
