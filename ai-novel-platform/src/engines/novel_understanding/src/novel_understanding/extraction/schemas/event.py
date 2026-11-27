from typing import Literal
from pydantic import BaseModel, Field
from .common import SourceEvidence, ExtractionProvenance

class EventParticipant(BaseModel):
    entity_mention_id: str
    role: str

class EventRecord(BaseModel):
    event_id: str
    document_id: str
    chunk_id: str
    event_type: str
    description: str
    participants: list[EventParticipant] = Field(default_factory=list)
    action: str | None = None
    object_mention_ids: list[str] = Field(default_factory=list)
    location_mention_ids: list[str] = Field(default_factory=list)
    temporal_expression: str | None = None
    evidence_status: Literal["explicit", "inferred", "uncertain"]
    source_evidence: list[SourceEvidence] = Field(min_length=1)
    provenance: ExtractionProvenance

class EventExtractionResponse(BaseModel):
    records: list[EventRecord] = Field(default_factory=list)
