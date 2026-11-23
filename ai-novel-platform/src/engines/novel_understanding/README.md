# Novel Understanding

TXT ingestion and source-preserving preprocessing for the AI Novel Assistant.

## Install

Python 3.12+

```powershell
python -m pip install -e ".[dev]"
```

## Ingest a novel

```powershell
python -m novel_understanding.ingestion.cli path/to/novel.txt --output-dir processed --document-id DOC_001
```

Ingestion preserves the decoded source and creates normalized text, paragraph
records, heading candidates, and a provider-neutral request for hierarchical
structure analysis. It does not assume every heading is a chapter. To validate
an analyzer's response:

```powershell
python -m novel_understanding.ingestion.cli novel.txt --output-dir processed --document-id DOC_001 --structure-result structure_result.json
```

Paragraph and structural offsets are zero-based, half-open character offsets
into `normalized.txt`. TXT files have no intrinsic page numbers.

## Preprocess ingestion output

The preprocessing stage segments paragraphs into sentence-like spans, assigns
provisional paragraph/segment labels, records quoted-span dialogue candidates,
and creates context-aware chunks. It does not identify speakers or call an LLM.
Source text is not rewritten.

```powershell
python -m novel_understanding.preprocessing.cli "processed\DOC_001\ingestion_v1" --output-dir processed_preprocessing --document-id DOC_001
```

Or, after installation:

```powershell
novel-preprocess "processed\DOC_001\ingestion_v1" --output-dir processed_preprocessing
```

Preprocessing outputs include paragraph annotations, sentence segments,
dialogue candidates, chunks, metadata, and a validation report. Source offsets
refer to `normalized.txt`; local offsets refer to the paragraph text. Chunk
token counts are approximations based on character length.

## Development

```powershell
python -m pytest -v
```
