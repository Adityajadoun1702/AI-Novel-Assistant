from pathlib import Path
import json
import pytest

from novel_understanding.ingestion.pipeline import IngestionPipeline
from novel_understanding.ingestion.exceptions import EmptyDocumentError, UnsupportedFileTypeError


def test_ingestion_does_not_assume_part_is_chapter(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("Chapter 1: Confusion\n\nOpening text.\n\nPart 1\n\nPart one text.\n\nPart 2\n\nPart two text.", encoding="utf-8")
    result = IngestionPipeline().process(source, document_id="DOC_TEST")
    assert [c.heading_text for c in result.heading_candidates] == ["Chapter 1: Confusion", "Part 1", "Part 2"]
    assert [c.role_hints for c in result.heading_candidates] == [["chapter"], ["part"], ["part"]]
    assert result.structure_analysis.status == "pending"
    assert len(result.paragraphs) == 6
    for p in result.paragraphs:
        assert result.normalized_text[p.start_offset:p.end_offset] == p.text


def test_heading_inside_same_block_is_split_without_text_loss(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("Chapter 1\nFirst paragraph.\nPart 1\nSecond paragraph.", encoding="utf-8")
    result = IngestionPipeline().process(source, document_id="DOC_SPLIT")
    assert [p.text for p in result.paragraphs] == ["Chapter 1", "First paragraph.", "Part 1", "Second paragraph."]


def test_single_line_breaks_stay_in_one_paragraph(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("Line one.\nLine two.\n\nNext paragraph.", encoding="utf-8")
    result = IngestionPipeline().process(source, document_id="DOC_LINES")
    assert len(result.paragraphs) == 2
    assert result.paragraphs[0].text == "Line one.\nLine two."


def test_no_headings_does_not_invent_chapter(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    result = IngestionPipeline().process(source, document_id="DOC_DEFAULT")
    assert len(result.heading_candidates) == 0
    assert result.structure_analysis.status == "pending"
    assert len(result.paragraphs) == 2


def test_utf8_bom(tmp_path: Path):
    source = tmp_path / "bom.txt"
    source.write_bytes("\ufeffHello — नमस्ते".encode("utf-8"))
    result = IngestionPipeline().process(source, document_id="DOC_BOM")
    assert result.metadata.had_utf8_bom is True
    assert result.paragraphs[0].text == "Hello — नमस्ते"


def test_empty_file_rejected(tmp_path: Path):
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")
    with pytest.raises(EmptyDocumentError):
        IngestionPipeline().process(source)


def test_non_txt_rejected(tmp_path: Path):
    source = tmp_path / "novel.pdf"
    source.write_bytes(b"not a pdf")
    with pytest.raises(UnsupportedFileTypeError):
        IngestionPipeline().process(source)


def test_save_outputs_candidate_and_ai_request_files(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("Chapter 1\n\nPart 1\n\nHello.", encoding="utf-8")
    pipeline = IngestionPipeline()
    result = pipeline.process(source, document_id="DOC_SAVE")
    output = pipeline.save(result, tmp_path / "processed")
    assert (output / "heading_candidates.json").exists()
    assert (output / "structure_request.json").exists()
    assert (output / "structure_prompt.md").exists()
    request = json.loads((output / "structure_request.json").read_text(encoding="utf-8"))
    assert len(request["heading_candidates"]) == 2
