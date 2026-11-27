import uuid
from pathlib import Path

from .adapters.preprocessing import PreprocessingAdapter
from .extractors.entity import EntityExtractor
from .schemas.entity import EntityExtractionResponse
from .storage_output import OutputWriter
from .validation import EvidenceValidator

SEGMENTS_PER_REQUEST = 3


class EntityExtractionPipeline:
    """Executable entity-only pipeline. Other extraction tasks are intentionally excluded."""

    def __init__(self, llm, input_adapter=None):
        self.llm = llm
        self.adapter = input_adapter or PreprocessingAdapter()
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
            "failed_batches": 0,
        }

        for chunk in chunks:
            state = {"chunk_id": chunk.chunk_id, "task": "entity", "status": "pending"}
            try:
                chunk_segments = [segment_by_id[sid] for sid in chunk.segment_ids]
                chunk_segments = [
                    segment for segment in chunk_segments
                    if segment.get("segment_type") != "heading"
                    and segment.get("paragraph_type") != "heading"
                ]
                records = []
                warnings = []
                successful_batches = 0
                failed_batches = 0
                for start in range(0, len(chunk_segments), SEGMENTS_PER_REQUEST):
                    batch = chunk_segments[start:start + SEGMENTS_PER_REQUEST]
                    try:
                        response = self.extractor.extract(
                            chunk=chunk,
                            segments=batch,
                            document_id=data.document_id,
                            normalized_text=data.normalized_text,
                            run_id=run_id,
                            extraction_version=version,
                        )
                    except Exception as exc:  # noqa: BLE001 - preserve other batches
                        failed_batches += 1
                        warnings.append(
                            f"Batch starting at segment {batch[0]['segment_id']} failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        continue
                    successful_batches += 1
                    records.extend(response.records)
                    warnings.extend(response.warnings)

                if failed_batches and successful_batches == 0:
                    totals["failed_batches"] += failed_batches
                    raise RuntimeError("Every entity extraction batch failed")

                response = EntityExtractionResponse(records=records, warnings=warnings)
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
                if failed_batches:
                    state["failed_batches"] = failed_batches
                    totals["failed_batches"] += failed_batches
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
