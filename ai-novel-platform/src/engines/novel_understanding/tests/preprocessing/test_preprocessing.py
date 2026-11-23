import json
from pathlib import Path

import pytest

from novel_preprocessing.pipeline import PreprocessingPipeline
from novel_preprocessing.segmenter import split_sentences
from novel_preprocessing.quote_detector import find_quoted_spans


def make_ingestion(tmp_path: Path):
    source = (
        "Chapter 1: Opening\n\n"
        'Horikita tilted her head. "What is wrong? Are you worried?" Sudou asked.\n\n'
        "I wondered if he was serious. Then I looked away."
    )
    root = tmp_path / "processed" / "DOC_TEST" / "ingestion_v1"
    root.mkdir(parents=True)
    paragraphs = [
        {
            "paragraph_id": "P001",
            "text": "Chapter 1: Opening",
            "start_offset": 0,
            "end_offset": 18,
            "is_heading_candidate": True,
            "chapter_id": "CH001",
        },
        {
            "paragraph_id": "P002",
            "text": 'Horikita tilted her head. "What is wrong? Are you worried?" Sudou asked.',
            "start_offset": 20,
            "end_offset": 91,
            "chapter_id": "CH001",
        },
        {
            "paragraph_id": "P003",
            "text": "I wondered if he was serious. Then I looked away.",
            "start_offset": 93,
            "end_offset": 143,
            "chapter_id": "CH001",
        },
    ]
    (root / "normalized.txt").write_text(source, encoding="utf-8")
    (root / "paragraphs.json").write_text(json.dumps(paragraphs), encoding="utf-8")
    (root / "metadata.json").write_text(
        json.dumps({"document_id": "DOC_TEST"}), encoding="utf-8"
    )
    (root / "heading_candidates.json").write_text(
        json.dumps([
            {
                "candidate_id": "HC001",
                "heading_text": "Chapter 1: Opening",
                "start_offset": 0,
                "end_offset": 18,
                "role_hints": ["chapter"],
            }
        ]),
        encoding="utf-8",
    )
    return root, source


def test_sentence_split_preserves_exact_slices():
    text = "Mr. A smiled. It was 3.14. Then he left!"
    spans = split_sentences(text)
    assert [span.text for span in spans] == [
        "Mr. A smiled.", "It was 3.14.", "Then he left!"
    ]
    assert all(text[span.start:span.end] == span.text for span in spans)


def test_quote_detector():
    spans = find_quoted_spans(
        'He said, “Hello.” Then she replied, "Goodbye."'
    )
    assert [span.text for span in spans] == ['“Hello.”', '"Goodbye."']


def test_multisentence_quote_is_one_candidate_linked_to_multiple_segments(tmp_path):
    ingestion, _ = make_ingestion(tmp_path)
    result = PreprocessingPipeline().run(ingestion, document_id="DOC_TEST")
    output = Path(result["output_directory"])

    candidates = json.loads(
        (output / "dialogue_candidates.json").read_text(encoding="utf-8")
    )
    matching = [
        item for item in candidates
        if item["text"] == '"What is wrong? Are you worried?"'
    ]

    assert len(matching) == 1
    assert len(matching[0]["segment_ids"]) >= 2


def test_heading_candidate_is_consumed(tmp_path):
    ingestion, _ = make_ingestion(tmp_path)
    result = PreprocessingPipeline().run(ingestion, document_id="DOC_TEST")
    output = Path(result["output_directory"])

    annotations = json.loads(
        (output / "paragraph_annotations.json").read_text(encoding="utf-8")
    )
    heading = next(item for item in annotations if item["paragraph_id"] == "P001")

    assert heading["paragraph_type"] == "heading"
    assert heading["classification_method"] == "ingestion_heading_candidate"


def test_pipeline_outputs_validate_and_preserve_source(tmp_path):
    ingestion, source = make_ingestion(tmp_path)
    result = PreprocessingPipeline(max_chunk_tokens=100).run(
        ingestion,
        output_dir=tmp_path / "custom_output",
        document_id="DOC_TEST",
    )
    output = Path(result["output_directory"])

    assert result["report"]["validation_passed"] is True
    assert (output / "chunks.json").exists()
    assert (output / "dialogue_candidates.json").exists()
    assert (ingestion / "normalized.txt").read_text(encoding="utf-8") == source


def test_default_output_goes_to_shared_processed_directory(tmp_path):
    ingestion, _ = make_ingestion(tmp_path)

    result = PreprocessingPipeline().run(ingestion)

    expected = tmp_path / "processed" / "DOC_TEST" / "preprocessing_v1"
    assert Path(result["output_directory"]) == expected


def test_no_overwrite(tmp_path):
    ingestion, _ = make_ingestion(tmp_path)
    PreprocessingPipeline().run(ingestion)
    with pytest.raises(FileExistsError):
        PreprocessingPipeline().run(ingestion)


def test_no_terminal_punctuation():
    spans = split_sentences("A sentence without punctuation")
    assert len(spans) == 1
    assert spans[0].text == "A sentence without punctuation"
