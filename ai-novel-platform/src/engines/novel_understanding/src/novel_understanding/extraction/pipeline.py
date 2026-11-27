import uuid
from pathlib import Path
from .adapters.preprocessing import PreprocessingAdapter
from .candidate_detection import CandidateDetector
from .extractors.entity import EntityExtractor
from .extractors.event import EventExtractor
from .extractors.relationship import RelationshipExtractor
from .extractors.context import ContextExtractor
from .validation import EvidenceValidator, ReferenceValidator
from .storage_output import OutputWriter

class ExtractionPipeline:
    def __init__(self, llm, input_adapter=None):
        self.llm = llm
        self.adapter = input_adapter or PreprocessingAdapter()
        self.detector = CandidateDetector()
        self.evidence = EvidenceValidator()
        self.references = ReferenceValidator()
        self.writer = OutputWriter()
        self.entity = EntityExtractor(llm); self.event = EventExtractor(llm)
        self.relationship = RelationshipExtractor(llm); self.context = ContextExtractor(llm)

    def run(self, input_dir, output_dir=None, document_id=None, version=1, max_chunks=None):
        data = self.adapter.load(input_dir, document_id)
        in_root = Path(data.input_dir)
        shared_root = Path(output_dir).resolve() if output_dir else in_root.parent.parent
        out = shared_root / data.document_id / f"extraction_v{version}"
        if out.exists(): raise FileExistsError(f"{out} exists; choose another extraction version")
        out.mkdir(parents=True)
        run_id = "EXT_" + uuid.uuid4().hex[:12].upper()
        chunks = data.chunks[:max_chunks] if max_chunks else data.chunks
        manifest = {"document_id": data.document_id, "run_id": run_id, "chunks": []}
        self.writer.store.write(out / "manifest.json", manifest)
        totals = {"completed": 0, "failed": 0}
        for chunk in chunks:
            state = {"chunk_id": chunk.chunk_id, "tasks": {}}
            try:
                candidates = self.detector.detect(chunk.text)
                ent = self.entity.extract(chunk, candidates)
                self._validate(ent.records, data, chunk.chunk_id)
                p = self.writer.write_task(out, "entities", chunk.chunk_id, "entity", ent)
                state["tasks"]["entity"] = {"status": "completed", "output": str(Path(p).relative_to(out))}
                ev = self.event.extract(chunk, ent)
                self._validate(ev.records, data, chunk.chunk_id)
                self._validate_refs(ev.records, {x.mention_id for x in ent.records})
                p = self.writer.write_task(out, "events", chunk.chunk_id, "event", ev)
                state["tasks"]["event"] = {"status": "completed", "output": str(Path(p).relative_to(out))}
                rel = self.relationship.extract(chunk, ent, ev)
                self._validate(rel.records, data, chunk.chunk_id)
                self._validate_refs(rel.records, {x.mention_id for x in ent.records})
                p = self.writer.write_task(out, "relationships", chunk.chunk_id, "relationship", rel)
                state["tasks"]["relationship"] = {"status": "completed", "output": str(Path(p).relative_to(out))}
                ctx = self.context.extract(chunk, ent, ev, rel)
                self._validate(ctx.records, data, chunk.chunk_id)
                self._validate_refs(ctx.records, {x.mention_id for x in ent.records})
                p = self.writer.write_task(out, "narrative_contexts", chunk.chunk_id, "context", ctx)
                state["tasks"]["context"] = {"status": "completed", "output": str(Path(p).relative_to(out))}
                state["status"] = "completed"; totals["completed"] += 1
            except Exception as exc:
                state["status"] = "failed"
                state["error"] = f"{type(exc).__name__}: {exc}"
                totals["failed"] += 1
            manifest["chunks"].append(state)
            self.writer.store.write(out / "manifest.json", manifest)
        report = {"document_id": data.document_id, "run_id": run_id,
                  "total_chunks": len(chunks), **totals,
                  "status": "completed" if totals["failed"] == 0 else "completed_with_warnings"}
        self.writer.store.write(out / "extraction_report.json", report)
        self.writer.store.write(out / "metadata.json", {
            "document_id": data.document_id, "extraction_version": version,
            "run_id": run_id, "provider": self.llm.provider, "model": self.llm.model,
            "strategy": "hybrid", "processing_unit": "chunk", "execution": "sequential",
            "prompt_versions": {"entity":"entity_v1","event":"event_v1",
                                "relationship":"relationship_v1","context":"context_v1"}
        })
        return {"output_directory": str(out), **report}

    def _validate(self, records, data, chunk_id):
        errors = self.evidence.validate(records, data.normalized_text, data.document_id, chunk_id)
        if errors: raise ValueError("; ".join(errors))

    def _validate_refs(self, records, entity_ids):
        errors = self.references.validate(records, entity_ids)
        if errors: raise ValueError("; ".join(errors))
