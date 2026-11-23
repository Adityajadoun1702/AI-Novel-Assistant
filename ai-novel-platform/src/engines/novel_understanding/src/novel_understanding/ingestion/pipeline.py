from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import ValidationError

from .chapter_detector import HeadingCandidateDetector
from .document_loader import DocumentLoader
from .exceptions import SourceValidationError
from .paragraph_segmenter import ParagraphSegmenter
from .schemas import (
    DocumentMetadata,
    IngestionReport,
    IngestionResult,
    StructureAnalysis,
)
from .structure_request import STRUCTURE_PROMPT, build_structure_request
from .text_normalizer import TextNormalizer
from .txt_extractor import TXTExtractor
from .validator import IngestionValidator


class IngestionPipeline:
    def __init__(self, loader=None, extractor=None, normalizer=None,
                 heading_detector=None, paragraph_segmenter=None, validator=None):
        self.loader = loader or DocumentLoader()
        self.extractor = extractor or TXTExtractor()
        self.normalizer = normalizer or TextNormalizer()
        self.heading_detector = heading_detector or HeadingCandidateDetector()
        self.paragraph_segmenter = paragraph_segmenter or ParagraphSegmenter()
        self.validator = validator or IngestionValidator()

    def process(self, file_path: str | Path, document_id: str | None = None,
                ingestion_version: int = 1, encoding: str | None = None,
                structure_result: str | Path | None = None) -> IngestionResult:
        if ingestion_version < 1:
            raise ValueError("ingestion_version must be >= 1")
        loaded = self.loader.load(file_path)
        file_hash = hashlib.sha256(loaded.data).hexdigest()
        decoded = self.extractor.extract(loaded.data, encoding)
        original_text = decoded.text
        normalized_text = self.normalizer.normalize(original_text)
        if not normalized_text.strip():
            from .exceptions import EmptyDocumentError
            raise EmptyDocumentError("The TXT file contains no readable text.")
        document_id = document_id or f"DOC_{file_hash[:12].upper()}"
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", document_id):
            raise ValueError("document_id must be 3-80 characters: letters, digits, '_' or '-'.")

        candidates = self.heading_detector.detect(normalized_text, document_id, ingestion_version)
        paragraphs = self.paragraph_segmenter.segment(
            normalized_text, document_id, ingestion_version, candidates
        )
        self.validator.validate(normalized_text, candidates, paragraphs)

        structure = StructureAnalysis()
        if structure_result:
            try:
                raw = json.loads(Path(structure_result).read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise SourceValidationError("Structure result must be a JSON object")
                # Older result files omitted status; supplying a result means the
                # analyzer claims completion, so default that one field explicitly.
                raw.setdefault("status", "completed")
                structure = StructureAnalysis.model_validate(raw)
            except (json.JSONDecodeError, OSError) as exc:
                raise SourceValidationError(f"Could not read structure result: {exc}") from exc
            except ValidationError as exc:
                raise SourceValidationError(f"Structure result does not match the schema: {exc}") from exc
            self.validator.validate_structure(normalized_text, structure, candidates)

        warnings = []
        if not candidates:
            warnings.append(
                "No explicit structural heading candidates found; document structure requires manual or AI review."
            )
        if decoded.confidence is not None and decoded.confidence < 0.50:
            warnings.append("Encoding detection confidence is low; verify the decoded text.")
        if structure.status == "pending":
            warnings.append(
                "Document hierarchy has not been inferred. Source validation passed, but structural validation has not run."
            )

        metadata = DocumentMetadata(
            document_id=document_id,
            document_name=Path(loaded.file_name).stem,
            file_name=loaded.file_name,
            file_hash=file_hash,
            encoding=decoded.encoding,
            encoding_source=decoded.source,
            encoding_confidence=decoded.confidence,
            had_utf8_bom=decoded.had_utf8_bom,
            ingestion_version=ingestion_version,
            normalization_version=TextNormalizer.VERSION,
            total_characters=len(normalized_text),
            total_paragraphs=len(paragraphs),
            total_heading_candidates=len(candidates),
        )
        report = IngestionReport(
            warnings=warnings,
            heading_candidate_count=len(candidates),
            paragraph_count=len(paragraphs),
            source_validation_passed=True,
            structure_validation_passed=True if structure.status == "completed" else None,
        )
        return IngestionResult(
            metadata=metadata,
            original_text=original_text,
            normalized_text=normalized_text,
            paragraphs=paragraphs,
            heading_candidates=candidates,
            structure_analysis=structure,
            report=report,
        )

    @staticmethod
    def save(result: IngestionResult, output_dir: str | Path) -> Path:
        target = Path(output_dir) / result.metadata.document_id / f"ingestion_v{result.metadata.ingestion_version}"
        target.mkdir(parents=True, exist_ok=False)
        (target / "original.txt").write_text(result.original_text, encoding="utf-8")
        (target / "normalized.txt").write_text(result.normalized_text, encoding="utf-8")
        (target / "metadata.json").write_text(result.metadata.model_dump_json(indent=2), encoding="utf-8")
        (target / "heading_candidates.json").write_text(json.dumps(
            [item.model_dump() for item in result.heading_candidates], ensure_ascii=False, indent=2), encoding="utf-8")
        (target / "paragraphs.json").write_text(json.dumps(
            [item.model_dump() for item in result.paragraphs], ensure_ascii=False, indent=2), encoding="utf-8")
        request = build_structure_request(
            result.metadata.document_id, result.heading_candidates, result.paragraphs
        )
        (target / "structure_request.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (target / "structure_prompt.md").write_text(STRUCTURE_PROMPT, encoding="utf-8")
        (target / "structure_analysis.json").write_text(
            result.structure_analysis.model_dump_json(indent=2), encoding="utf-8"
        )
        (target / "ingestion_report.json").write_text(
            result.report.model_dump_json(indent=2), encoding="utf-8"
        )
        return target
