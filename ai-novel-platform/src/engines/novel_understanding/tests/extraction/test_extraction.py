import json
from pathlib import Path
from types import SimpleNamespace

from novel_understanding.extraction.adapters.preprocessing import PreprocessingAdapter
from novel_understanding.extraction.entity_pipeline import EntityExtractionPipeline
from novel_understanding.extraction.extractors.entity import EntityExtractor
from novel_understanding.extraction.integrations.mock_llm import MockLLMAdapter
from novel_understanding.extraction.pipeline import ExtractionPipeline


def make_preprocessing_output(tmp_path: Path) -> Path:
    document_root = tmp_path / "processed" / "DOC_TEST"
    root = document_root / "preprocessing_v1"
    root.mkdir(parents=True)
    ingestion = document_root / "ingestion_v1"
    ingestion.mkdir()

    (root / "preprocessing_metadata.json").write_text(
        json.dumps({
            "document_id": "DOC_TEST",
            "input_directory": str(ingestion),
        }),
        encoding="utf-8",
    )
    (ingestion / "normalized.txt").write_text("Alice ran.", encoding="utf-8")
    (ingestion / "metadata.json").write_text(
        json.dumps({"document_id": "DOC_TEST"}),
        encoding="utf-8",
    )
    (ingestion / "paragraphs.json").write_text(
        json.dumps([
            {
                "paragraph_id": "P001",
                "text": "Alice ran.",
                "start_offset": 0,
                "end_offset": 10,
            }
        ]),
        encoding="utf-8",
    )
    (root / "sentence_segments.json").write_text(
        json.dumps([
            {
                "segment_id": "SEG_P001_0001",
                "paragraph_id": "P001",
                "text": "Alice ran.",
                "source_ref": {
                    "source_start": 0,
                    "source_end": 10,
                },
            }
        ]),
        encoding="utf-8",
    )
    (root / "dialogue_candidates.json").write_text("[]", encoding="utf-8")
    (root / "chunks.json").write_text(
        json.dumps([
            {
                "chunk_id": "CHK_000001",
                "text": "Alice ran.",
                "source_map": [
                    {
                        "paragraph_id": "P001",
                        "segment_ids": ["SEG_P001_0001"],
                    }
                ],
            }
        ]),
        encoding="utf-8",
    )
    return root


def test_adapter_reads_preprocessing_metadata_and_chunk_source_map(tmp_path):
    root = make_preprocessing_output(tmp_path)

    data = PreprocessingAdapter().load(root)

    assert data.document_id == "DOC_TEST"
    assert data.normalized_text == "Alice ran."
    assert data.chunks[0].paragraph_ids == ["P001"]
    assert data.chunks[0].segment_ids == ["SEG_P001_0001"]

def test_adapter_uses_ingestion_version_linked_by_preprocessing_metadata(tmp_path):
    root = make_preprocessing_output(tmp_path)
    newer_ingestion = root.parent / "ingestion_v2"
    newer_ingestion.mkdir()
    (newer_ingestion / "metadata.json").write_text(
        json.dumps({"document_id": "DOC_TEST"}),
        encoding="utf-8",
    )
    (newer_ingestion / "normalized.txt").write_text("Wrong source.", encoding="utf-8")
    (newer_ingestion / "paragraphs.json").write_text("[]", encoding="utf-8")

    data = PreprocessingAdapter().load(root)

    assert Path(data.ingestion_dir).name == "ingestion_v1"
    assert data.normalized_text == "Alice ran."


def test_adapter_marks_heading_segments_from_paragraph_annotations(tmp_path):
    root = make_preprocessing_output(tmp_path)
    (root / "paragraph_annotations.json").write_text(
        json.dumps([{"paragraph_id": "P001", "paragraph_type": "heading"}]),
        encoding="utf-8",
    )

    data = PreprocessingAdapter().load(root)

    assert data.segments[0]["paragraph_type"] == "heading"


def test_mock_pipeline_writes_output_under_shared_processed_directory(tmp_path):
    input_dir = make_preprocessing_output(tmp_path)

    result = ExtractionPipeline(MockLLMAdapter()).run(input_dir, max_chunks=1)

    output = Path(result["output_directory"])
    assert output == tmp_path / "processed" / "DOC_TEST" / "extraction_v1"
    assert result["status"] == "completed"
    assert result["total_chunks"] == 1
    assert (output / "manifest.json").exists()
    assert (output / "extraction_report.json").exists()
    assert (output / "entities" / "CHK_000001.json").exists()


class OneMentionLLM:
    provider = "test"
    model = "test-model"

    def generate_structured(
        self, *, system_prompt, user_prompt, response_schema, temperature=0.0
    ):
        return response_schema.model_validate({
            "mentions": [{
                "segment_id": "SEG_P001_0001",
                "surface_text": "Alice",
                "entity_type": "person",
                "mention_kind": "proper_name",
                "confidence": 0.9,
            }, {
                "segment_id": "SEG_P001_0001",
                "surface_text": "Missing",
                "entity_type": "person",
                "mention_kind": "proper_name",
                "confidence": 0.7,
            }]
        })


def test_entity_pipeline_writes_model_extracted_mentions_with_source_evidence(tmp_path):
    input_dir = make_preprocessing_output(tmp_path)

    result = EntityExtractionPipeline(OneMentionLLM()).run(
        input_dir,
        max_chunks=1,
        version=3,
    )

    output = Path(result["output_directory"])
    records = json.loads(
        (output / "entities" / "CHK_000001.json").read_text(encoding="utf-8")
    )["records"]
    assert result["mentions"] == 1
    assert result["rejected_candidates"] == 1
    assert result["status"] == "completed_with_warnings"
    assert records[0]["surface_text"] == "Alice"
    assert records[0]["source_evidence"][0]["start_offset"] == 0
    assert records[0]["source_evidence"][0]["exact_text"] == "Alice"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["chunks"][0]["status"] == "completed"
    assert len(manifest["chunks"][0]["warnings"]) == 1


def test_entity_pipeline_keeps_successful_batches_when_another_batch_fails(tmp_path):
    source_parts = ["Alice arrived.", "Bob waved.", "The bell rang.", "Horikita smiled."]
    text = " ".join(source_parts)
    segments = []
    offset = 0
    for index, part in enumerate(source_parts, start=1):
        segments.append({
            "segment_id": f"SEG_{index}",
            "paragraph_id": f"P_{index}",
            "segment_type": "narration",
            "text": part,
            "source_ref": {"source_start": offset, "source_end": offset + len(part)},
        })
        offset += len(part) + 1

    input_dir = tmp_path / "processed" / "DOC_BATCH" / "preprocessing_v1"
    input_dir.mkdir(parents=True)
    data = SimpleNamespace(
        input_dir=str(input_dir),
        ingestion_dir=str(input_dir.parent / "ingestion_v1"),
        document_id="DOC_BATCH",
        normalized_text=text,
        segments=segments,
        chunks=[SimpleNamespace(
            chunk_id="CHK_1",
            segment_ids=[segment["segment_id"] for segment in segments],
        )],
    )

    class FlakyBatchLLM:
        provider = "test"
        model = "test-model"

        def __init__(self):
            self.calls = 0

        def generate_structured(
            self, *, system_prompt, user_prompt, response_schema, temperature=0.0
        ):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary model error")
            return response_schema.model_validate({
                "mentions": [{
                    "segment_id": "SEG_4",
                    "surface_text": "Horikita",
                    "entity_type": "person",
                    "mention_kind": "proper_name",
                }]
            })

    model = FlakyBatchLLM()

    class InputAdapter:
        def load(self, input_dir, expected_document_id=None):
            return data

    result = EntityExtractionPipeline(model, input_adapter=InputAdapter()).run(
        input_dir,
        version=4,
    )

    output = Path(result["output_directory"])
    records = json.loads(
        (output / "entities" / "CHK_1.json").read_text(encoding="utf-8")
    )["records"]
    assert model.calls == 2
    assert result["failed"] == 0
    assert result["failed_batches"] == 1
    assert result["mentions"] == 1
    assert result["status"] == "completed_with_warnings"
    assert records[0]["surface_text"] == "Horikita"


def test_entity_extractor_rejects_fragments_and_corrects_human_pronouns():
    class NoisyLLM:
        provider = "test"
        model = "test-model"

        def generate_structured(
            self, *, system_prompt, user_prompt, response_schema, temperature=0.0
        ):
            return response_schema.model_validate({
                "mentions": [
                    {
                        "segment_id": "SEG_1",
                        "surface_text": "Horikita",
                        "entity_type": "person",
                        "mention_kind": "proper_name",
                    },
                    {
                        "segment_id": "SEG_1",
                        "surface_text": "questioned",
                        "entity_type": "other",
                        "mention_kind": "description",
                    },
                    {
                        "segment_id": "SEG_1",
                        "surface_text": "the whole sentence.",
                        "entity_type": "other",
                        "mention_kind": "unknown",
                    },
                    {
                        "segment_id": "SEG_1",
                        "surface_text": "her",
                        "entity_type": "other",
                        "mention_kind": "pronoun",
                    },
                ]
            })

    text = "Horikita questioned her."
    segment = {
        "segment_id": "SEG_1",
        "paragraph_id": "P1",
        "text": text,
        "source_ref": {"source_start": 0, "source_end": len(text)},
    }

    result = EntityExtractor(NoisyLLM()).extract(
        chunk=SimpleNamespace(chunk_id="CHK_1"),
        segments=[segment],
        document_id="DOC_1",
        normalized_text=text,
        run_id="RUN_1",
        extraction_version=5,
    )

    assert [record.surface_text for record in result.records] == ["Horikita", "her"]
    assert result.records[1].entity_type == "person"
    assert len(result.warnings) == 2


class RepeatedMentionLLM:
    provider = "test"
    model = "test-model"

    def generate_structured(
        self, *, system_prompt, user_prompt, response_schema, temperature=0.0
    ):
        return response_schema.model_validate({
            "mentions": [{
                "segment_id": "SEG_1",
                "surface_text": "gymnasium",
                "entity_type": "place",
                "mention_kind": "nominal_reference",
            }]
        })


def test_entity_extractor_expands_surface_text_without_model_occurrence_indices():
    text = "The gymnasium opened. The gymnasium closed."
    segment = {
        "segment_id": "SEG_1",
        "paragraph_id": "P1",
        "text": text,
        "source_ref": {"source_start": 0, "source_end": len(text)},
    }

    result = EntityExtractor(RepeatedMentionLLM()).extract(
        chunk=SimpleNamespace(chunk_id="CHK_1"),
        segments=[segment],
        document_id="DOC_1",
        normalized_text=text,
        run_id="RUN_1",
        extraction_version=3,
    )

    assert [record.source_evidence[0].start_offset for record in result.records] == [4, 26]
    assert [record.source_evidence[0].exact_text for record in result.records] == [
        "gymnasium",
        "gymnasium",
    ]
