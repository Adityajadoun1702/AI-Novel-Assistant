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
                "occurrence_index": 2,
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
