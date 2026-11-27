from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


SpanType = Literal["narration", "dialogue", "internal_thought", "heading", "footnote", "unknown"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    paragraph_id: str
    local_start: int = Field(ge=0)
    local_end: int = Field(ge=0)
    source_start: int | None = Field(default=None, ge=0)
    source_end: int | None = Field(default=None, ge=0)


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_id: str
    paragraph_id: str
    sequence: int = Field(ge=0)
    segment_type: SpanType
    text: str
    source_ref: SourceRef
    classification_method: str
    confidence: float = Field(ge=0, le=1)


class ParagraphAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraph_id: str
    paragraph_type: SpanType
    chapter_id: str | None = None
    segment_ids: list[str]
    classification_method: str
    confidence: float = Field(ge=0, le=1)


class DialogueCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str
    paragraph_id: str
    segment_ids: list[str] = Field(min_length=1)
    text: str
    quote_style: str
    source_ref: SourceRef
    speaker_id: str | None = None
    speaker_status: Literal["unassigned"] = "unassigned"
    confidence: float = Field(ge=0, le=1)


class ChunkSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraph_id: str
    segment_ids: list[str]
    source_start: int | None = None
    source_end: int | None = None


class ContextChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    sequence: int = Field(ge=0)
    chapter_id: str | None = None
    text: str
    estimated_tokens: int = Field(ge=0)
    source_map: list[ChunkSource]
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None
