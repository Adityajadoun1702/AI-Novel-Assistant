import json
from pathlib import Path

import pytest

from novel_preprocessing.pipeline import PreprocessingPipeline
from novel_preprocessing.segmenter import split_sentences
from novel_preprocessing.quote_detector import find_quoted_spans


def make_ingestion(tmp_path: Path):
    source = (
        "Chapter 1: Opening\n\n"
        'Horikita tilted her head. "What is wrong?" Sudou asked.\n\n'
        "I wondered if he was serious. Then I looked away."
    )
    root = tmp_path / "ingestion_v1"
    root.mkdir()
    (root / "normalized.txt").write_text(source, encoding="utf-8")
    paragraphs = [
        {"paragraph_id": "P001", "text": "Chapter 1: Opening", "start_offset": 0, "end_offset": 18,
         "paragraph_type": "chapter_heading", "chapter_id": "CH001"},
        {"paragraph_id": "P002", "text": 'Horikita tilted her head. "What is wrong?" Sudou asked.',
         "start_offset": 20, "end_offset": 75, "chapter_id": "CH001"},
        {"paragraph_id": "P003", "text": "I wondered if he was serious. Then I looked away.",
         "start_offset": 77, "end_offset": 127, "chapter_id": "CH001"},
    ]
    (root / "paragraphs.json").write_text(json.dumps(paragraphs), encoding="utf-8")
    (root / "metadata.json").write_text(json.dumps({"document_id": "DOC_TEST"}), encoding="utf-8")
    return root, source


def test_sentence_split_preserves_exact_slices():
    text = "Mr. A smiled. It was 3.14. Then he left!"
    spans = split_sentences(text)
    assert [s.text for s in spans] == ["Mr. A smiled.", "It was 3.14.", "Then he left!"]
    assert all(text[s.start:s.end] == s.text for s in spans)


def test_quote_detector():
    spans = find_quoted_spans('He said, “Hello.” Then she replied, "Goodbye."')
    assert [x.text for x in spans] == ['“Hello.”', '"Goodbye."']


def test_pipeline_outputs_and_validates(tmp_path):
    ingestion, source = make_ingestion(tmp_path)
    result = PreprocessingPipeline(max_chunk_tokens=100).run(
        ingestion, tmp_path / "out", document_id="DOC_TEST"
    )
    out = Path(result["output_directory"])
    assert result["report"]["validation_passed"] is True
    assert (out / "chunks.json").exists()
    assert (out / "dialogue_candidates.json").exists()
    assert (ingestion / "normalized.txt").read_text(encoding="utf-8") == source
    candidates = json.loads((out / "dialogue_candidates.json").read_text(encoding="utf-8"))
    assert candidates[0]["text"] == '"What is wrong?"'


def test_no_overwrite(tmp_path):
    ingestion, _ = make_ingestion(tmp_path)
    output = tmp_path / "out"
    PreprocessingPipeline().run(ingestion, output, document_id="DOC_TEST")
    with pytest.raises(FileExistsError):
        PreprocessingPipeline().run(ingestion, output, document_id="DOC_TEST")


def test_no_terminal_punctuation():
    spans = split_sentences("A sentence without punctuation")
    assert len(spans) == 1
    assert spans[0].text == "A sentence without punctuation"
def test_default_output_goes_to_shared_processed_directory(tmp_path):
    ingestion_dir = tmp_path / "processed" / "DOC_TEST" / "ingestion_v1"
    ingestion_dir.mkdir(parents=True)

    (ingestion_dir / "paragraphs.json").write_text("[]", encoding="utf-8")
    (ingestion_dir / "metadata.json").write_text(
        '{"document_id": "DOC_TEST"}',
        encoding="utf-8"
    )

    result = PreprocessingPipeline().run(ingestion_dir)

    expected = (
        tmp_path / "processed" / "DOC_TEST" / "preprocessing_v1"
    )

    assert Path(result["output_directory"]) == expected
