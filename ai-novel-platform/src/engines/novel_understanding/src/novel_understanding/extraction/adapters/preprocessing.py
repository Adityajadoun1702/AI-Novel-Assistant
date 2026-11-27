import json
import re
from pathlib import Path

from pydantic import BaseModel, Field


def read_json(path: Path, required: bool = True):
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def unwrap(value, key: str):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for candidate in (key, "items", "records", "data"):
            if isinstance(value.get(candidate), list):
                return value[candidate]
    raise ValueError(f"Expected an array or object containing '{key}'")


class Chunk(BaseModel):
    chunk_id: str
    text: str
    paragraph_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class InputData(BaseModel):
    input_dir: str
    ingestion_dir: str
    document_id: str
    metadata: dict
    normalized_text: str
    paragraphs: list[dict]
    segments: list[dict]
    dialogue_candidates: list[dict]
    chunks: list[Chunk]


class PreprocessingAdapter:
    """Loads the actual sibling ingestion_vN and preprocessing_vN directories."""

    def load(self, input_dir, expected_document_id=None):
        root = Path(input_dir).resolve()
        if not root.is_dir():
            raise NotADirectoryError(root)

        preprocessing_metadata = read_json(root / "preprocessing_metadata.json")
        doc_id = preprocessing_metadata.get("document_id")
        if not doc_id:
            raise ValueError("preprocessing_metadata.json is missing document_id")
        if expected_document_id and doc_id != expected_document_id:
            raise ValueError(f"Expected document {expected_document_id}, got {doc_id}")

        # Current project layout: processed/DOC_ID/{ingestion_vN,preprocessing_vN}
        # Do not rely on the absolute input_directory stored on another machine.
        doc_root = root.parent
        ingestion_dirs = [
            p for p in doc_root.glob("ingestion_v*")
            if p.is_dir() and re.fullmatch(r"ingestion_v\d+", p.name)
        ]
        if not ingestion_dirs:
            raise FileNotFoundError(
                f"No ingestion_v* directory found beside {root}. "
                "Expected processed/DOC_ID/ingestion_vN and preprocessing_vN."
            )
        ingestion_dirs.sort(key=lambda path: int(path.name.removeprefix("ingestion_v")))
        input_directory = preprocessing_metadata.get("input_directory")
        requested_name = (
            Path(str(input_directory).replace("\\", "/")).name
            if input_directory
            else None
        )
        ingestion_dir = next(
            (path for path in ingestion_dirs if path.name == requested_name),
            ingestion_dirs[-1],
        )

        metadata = read_json(ingestion_dir / "metadata.json")
        if metadata.get("document_id") != doc_id:
            raise ValueError("Ingestion and preprocessing document IDs do not match")

        # Path.read_text uses universal-newline translation, matching LF-normalized offsets.
        normalized_text = (ingestion_dir / "normalized.txt").read_text(encoding="utf-8")
        paragraphs = unwrap(read_json(ingestion_dir / "paragraphs.json"), "paragraphs")
        segments = unwrap(read_json(root / "sentence_segments.json"), "segments")
        dialogue = unwrap(read_json(root / "dialogue_candidates.json", False), "dialogue_candidates")
        chunks_raw = unwrap(read_json(root / "chunks.json"), "chunks")

        segment_by_id = {}
        for item in segments:
            sid = item.get("segment_id")
            ref = item.get("source_ref") or {}
            if not sid or not isinstance(ref.get("source_start"), int) or not isinstance(ref.get("source_end"), int):
                raise ValueError(f"Invalid sentence segment source mapping: {sid!r}")
            start, end = ref["source_start"], ref["source_end"]
            if start < 0 or end <= start or end > len(normalized_text):
                raise ValueError(f"Invalid offsets for segment {sid}")
            exact = normalized_text[start:end]
            if exact != item.get("text"):
                raise ValueError(
                    f"Segment/source mismatch for {sid}: offsets do not reproduce segment text"
                )
            segment_by_id[sid] = item

        chunks = []
        for index, item in enumerate(chunks_raw):
            chunk_id = item.get("chunk_id") or item.get("id")
            text = item.get("text") or item.get("content")
            if not chunk_id or text is None:
                raise ValueError(f"Chunk {index} must contain chunk_id and text")
            source_map = item.get("source_map") or []
            segment_ids = []
            paragraph_ids = []
            for source in source_map:
                pid = source.get("paragraph_id")
                if pid and str(pid) not in paragraph_ids:
                    paragraph_ids.append(str(pid))
                for sid in source.get("segment_ids", []):
                    if str(sid) not in segment_ids:
                        segment_ids.append(str(sid))
            missing = [sid for sid in segment_ids if sid not in segment_by_id]
            if missing:
                raise ValueError(f"Chunk {chunk_id} references unknown segments: {missing[:3]}")
            chunks.append(Chunk(
                chunk_id=str(chunk_id),
                text=str(text),
                paragraph_ids=paragraph_ids,
                segment_ids=segment_ids,
                raw=item,
            ))

        return InputData(
            input_dir=str(root),
            ingestion_dir=str(ingestion_dir),
            document_id=str(doc_id),
            metadata=metadata,
            normalized_text=normalized_text,
            paragraphs=paragraphs,
            segments=segments,
            dialogue_candidates=dialogue,
            chunks=chunks,
        )
