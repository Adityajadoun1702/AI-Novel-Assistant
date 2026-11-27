import uuid
from pathlib import Path

from .adapters.preprocessing import PreprocessingAdapter
from .candidate_detection import CandidateDetector
from .extractors.entity import EntityExtractor
from .storage_output import OutputWriter
from .validation import EvidenceValidator


class EntityExtractionPipeline:
    """Executable entity-only pipeline. Other extraction tasks are intentionally excluded."""

    def __init__(self, llm, input_adapter=None):
        self.llm = llm
        self.adapter = input_adapter or PreprocessingAdapter()
        self.detector = CandidateDetector()
        self.extractor = EntityExtractor(llm)
        self.evidence_validator = EvidenceValidator()
        self.writer = OutputWriter()

    def run(
        self,
        input_dir,
        output_dir=None,
        document_id=None,
        version=2,
        max_chunks=None,
    ):
        data = self.adapter.load(input_dir, document_id)
        input_root = Path(data.input_dir)
        # preprocessing_v2 is nested under processed/DOC_ID, so parent is shared processed root.
        shared_root = Path(output_dir).resolve() if output_dir else input_root.parent.parent
        output_root = shared_root / data.document_id / f"extraction_v{version}"
        if output_root.exists():
            raise FileExistsError(
                f"{output_root} already exists. Choose another --version; outputs are never overwritten."
            )

        run_id = "ENT_" + uuid.uuid4().hex[:12].upper()
        chunks = data.chunks[:max_chunks] if max_chunks else data.chunks
        segment_by_id = {item["segment_id"]: item for item in data.segments}
        output_root.mkdir(parents=True)

        manifest = {
            "document_id": data.document_id,
            "run_id": run_id,
            "extraction_version": version,
            "scope": "entity_mentions_only",
            "chunks": [],
        }
        self.writer.store.write(output_root / "manifest.json", manifest)
        totals = {
            "completed": 0,
            "failed": 0,
            "mentions": 0,
            "rejected_candidates": 0,
        }

        for chunk in chunks:
            state = {"chunk_id": chunk.chunk_id, "task": "entity", "status": "pending"}
            try:
                chunk_segments = [
                    segment_by_id[sid] for sid in chunk.segment_ids
                ]
                hints = self.detector.detect(chunk.text).model_dump(mode="json")
                response = self.extractor.extract(
                    chunk=chunk,
                    segments=chunk_segments,
                    document_id=data.document_id,
                    normalized_text=data.normalized_text,
                    run_id=run_id,
                    extraction_version=version,
                    candidate_hints=hints.get("candidates", []),
                )
                errors = self.evidence_validator.validate(
                    response.records,
                    data.normalized_text,
                    data.document_id,
                    chunk.chunk_id,
                )
                if errors:
                    raise ValueError("; ".join(errors))

                path = self.writer.write_task(
                    output_root, "entities", chunk.chunk_id, "entity", response
                )
                state.update({
                    "status": "completed",
                    "output": str(Path(path).relative_to(output_root)),
                    "record_count": len(response.records),
                })
                if response.warnings:
                    state["warnings"] = response.warnings
                    totals["rejected_candidates"] += len(response.warnings)
                totals["completed"] += 1
                totals["mentions"] += len(response.records)
            except Exception as exc:  # noqa: BLE001 - record this chunk failure and continue
                state.update({
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                totals["failed"] += 1
            manifest["chunks"].append(state)
            self.writer.store.write(output_root / "manifest.json", manifest)

        report = {
            "document_id": data.document_id,
            "run_id": run_id,
            "extraction_version": version,
            "scope": "entity_mentions_only",
            "total_chunks": len(chunks),
            **totals,
            "status": (
                "completed"
                if totals["failed"] == 0 and totals["rejected_candidates"] == 0
                else "completed_with_warnings"
            ),
            "semantic_extraction_performed": self.llm.provider != "mock",
        }
        metadata = {
            "document_id": data.document_id,
            "extraction_version": version,
            "run_id": run_id,
            "provider": self.llm.provider,
            "model": self.llm.model,
            "strategy": "llm_semantics_with_deterministic_source_grounding",
            "processing_unit": "chunk",
            "execution": "sequential",
            "prompt_versions": {"entity": EntityExtractor.prompt_version},
            "input_preprocessing_directory": str(input_root),
            "input_ingestion_directory": data.ingestion_dir,
        }
        self.writer.store.write(output_root / "metadata.json", metadata)
        self.writer.store.write(output_root / "extraction_report.json", report)
        return {"output_directory": str(output_root), **report}
