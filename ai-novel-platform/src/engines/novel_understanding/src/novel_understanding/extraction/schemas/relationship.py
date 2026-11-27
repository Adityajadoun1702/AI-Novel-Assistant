from typing import Literal
from pydantic import BaseModel, Field
from .common import SourceEvidence, ExtractionProvenance

class RelationshipRecord(BaseModel):
    relationship_id: str
    document_id: str
    chunk_id: str
    source_entity_mention_id: str
    target_entity_mention_id: str
    relationship_type: str
    description: str | None = None
    temporal_scope: str | None = None
    evidence_status: Literal["explicit", "inferred", "uncertain"]
    source_evidence: list[SourceEvidence] = Field(min_length=1)
    provenance: ExtractionProvenance

class RelationshipExtractionResponse(BaseModel):
    records: list[RelationshipRecord] = Field(default_factory=list)
