from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


StructureType = Literal[
    "volume", "book", "chapter", "part", "section", "subsection",
    "prologue", "epilogue", "interlude", "appendix", "other",
]

CandidateClassificationType = Literal[
    "volume", "book", "chapter", "part", "section", "subsection",
    "prologue", "epilogue", "interlude", "appendix", "other",
    "not_a_heading", "uncertain",
]


class HeadingCandidate(StrictModel):
    candidate_id: str
    heading_text: str
    line_number: int = Field(ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    role_hints: list[str] = Field(default_factory=list)
    detector_version: str
    evidence: list[str] = Field(default_factory=list)


class ParagraphRecord(StrictModel):
    paragraph_id: str
    document_id: str
    sequence_number: int = Field(ge=1)
    text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    source_line_start: int = Field(ge=1)
    source_line_end: int = Field(ge=1)
    is_heading_candidate: bool = False
    heading_candidate_id: str | None = None


class CandidateClassification(StrictModel):
    candidate_id: str
    classification: CandidateClassificationType
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class StructuralUnit(StrictModel):
    """A half-open source range [start_offset, end_offset)."""

    unit_id: str
    unit_type: StructureType
    title: str
    heading_candidate_id: str | None = None
    parent_unit_id: str | None = None
    # Order is 1-based among units with the same parent (including root units).
    order: int = Field(ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class StructureAnalysis(StrictModel):
    status: Literal["pending", "completed"] = "pending"
    candidate_classifications: list[CandidateClassification] = Field(default_factory=list)
    units: list[StructuralUnit] = Field(default_factory=list)
    unresolved_candidate_ids: list[str] = Field(default_factory=list)
    analyzer: str = "not_run"


class DocumentMetadata(StrictModel):
    document_id: str
    document_name: str
    file_name: str
    file_format: Literal["txt"] = "txt"
    file_hash: str
    encoding: str
    encoding_source: str
    encoding_confidence: float | None = None
    had_utf8_bom: bool = False
    language: str | None = None
    ingestion_version: int = Field(ge=1)
    normalization_version: str
    total_characters: int = Field(ge=0)
    total_paragraphs: int = Field(ge=0)
    total_heading_candidates: int = Field(ge=0)
    ingestion_status: Literal["completed"] = "completed"


class IngestionReport(StrictModel):
    warnings: list[str] = Field(default_factory=list)
    heading_candidate_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)
    source_validation_passed: bool
    # None means structural analysis has not been run, not that it passed.
    structure_validation_passed: bool | None = None


class IngestionResult(StrictModel):
    metadata: DocumentMetadata
    original_text: str
    normalized_text: str
    paragraphs: list[ParagraphRecord]
    heading_candidates: list[HeadingCandidate]
    structure_analysis: StructureAnalysis
    report: IngestionReport
