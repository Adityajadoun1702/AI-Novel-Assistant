import json
from pathlib import Path
from pydantic import BaseModel, Field

def read_json(path, required=True):
    p = Path(path)
    if not p.exists():
        if required: raise FileNotFoundError(p)
        return None
    return json.loads(p.read_text(encoding="utf-8"))

def unwrap(value, key):
    if value is None: return []
    if isinstance(value, list): return value
    if isinstance(value, dict):
        for k in (key, "items", "records", "data"):
            if isinstance(value.get(k), list): return value[k]
    raise ValueError(f"Expected array or object containing {key}")

class Chunk(BaseModel):
    chunk_id: str
    text: str
    paragraph_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)

class InputData(BaseModel):
    input_dir: str
    document_id: str
    metadata: dict
    normalized_text: str
    paragraphs: list[dict]
    segments: list[dict]
    dialogue_candidates: list[dict]
    chunks: list[Chunk]

class PreprocessingAdapter:
    def load(self, input_dir, expected_document_id=None):
        root = Path(input_dir).resolve()
        metadata = read_json(root / "metadata.json")
        doc_id = metadata.get("document_id")
        if not doc_id: raise ValueError("metadata.json missing document_id")
        if expected_document_id and doc_id != expected_document_id:
            raise ValueError(f"Expected {expected_document_id}, got {doc_id}")
        source = (root / "normalized.txt").read_text(encoding="utf-8")
        paragraphs = unwrap(read_json(root / "paragraphs.json"), "paragraphs")
        chunks_raw = unwrap(read_json(root / "chunks.json"), "chunks")
        segments = unwrap(read_json(root / "sentence_segments.json", False), "segments")
        dialogue = unwrap(read_json(root / "dialogue_candidates.json", False), "dialogue_candidates")
        chunks = []
        for i, item in enumerate(chunks_raw):
            cid = item.get("chunk_id") or item.get("id")
            text = item.get("text") or item.get("content")
            if not cid or text is None:
                raise ValueError(f"Chunk {i} must contain chunk_id/id and text/content")
            chunks.append(Chunk(
                chunk_id=str(cid), text=str(text),
                paragraph_ids=[str(x) for x in item.get("paragraph_ids", item.get("source_paragraph_ids", []))],
                segment_ids=[str(x) for x in item.get("segment_ids", item.get("source_segment_ids", []))],
                raw=item
            ))
        return InputData(input_dir=str(root), document_id=str(doc_id), metadata=metadata,
                         normalized_text=source, paragraphs=paragraphs, segments=segments,
                         dialogue_candidates=dialogue, chunks=chunks)
