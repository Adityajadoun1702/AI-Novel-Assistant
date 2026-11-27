from pydantic import BaseModel, Field
from .common import SourceEvidence, ExtractionProvenance

class NarrativeContext(BaseModel):
    context_id: str
    document_id: str
    chunk_id: str
    summary: str
    involved_entity_mention_ids: list[str] = Field(default_factory=list)
    related_event_ids: list[str] = Field(default_factory=list)
    location_mention_ids: list[str] = Field(default_factory=list)
    temporal_context: str | None = None
    situation_type: str | None = None
    unresolved_questions: list[str] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(min_length=1)
    provenance: ExtractionProvenance

class ContextExtractionResponse(BaseModel):
    records: list[NarrativeContext] = Field(default_factory=list)
