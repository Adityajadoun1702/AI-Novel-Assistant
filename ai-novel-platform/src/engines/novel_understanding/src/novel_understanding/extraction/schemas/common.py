from typing import Literal
from pydantic import BaseModel, Field, model_validator

class SourceEvidence(BaseModel):
    document_id: str
    chunk_id: str
    paragraph_ids: list[str] = Field(min_length=1)
    segment_ids: list[str] = Field(default_factory=list)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    exact_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must exceed start_offset")
        if len(self.exact_text) != self.end_offset - self.start_offset:
            raise ValueError("exact_text length must match offset range")
        return self

class ExtractionProvenance(BaseModel):
    method: Literal["rule_based", "nlp", "llm", "hybrid"] = "hybrid"
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    extraction_version: str
    extraction_run_id: str
    confidence: float | None = Field(default=None, ge=0, le=1)
