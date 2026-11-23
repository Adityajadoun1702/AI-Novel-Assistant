# Novel Preprocessing Engine — v0.1

A deterministic, source-preserving preprocessing module for the AI Novel Assistant.
It consumes the JSON output of the TXT Ingestion module and creates annotations that
make later narrative extraction easier.

## What it does

1. Reads paragraph records from an ingestion output directory.
2. Segments each paragraph into sentence-like spans while retaining exact source offsets.
3. Classifies paragraph and segment spans using conservative heuristics:
   `narration`, `dialogue`, `internal_thought`, `heading`, `footnote`, or `unknown`.
4. Detects quoted spans and records them as dialogue candidates. It does **not** identify
   the speaker.
5. Creates context-aware chunks from sentence/paragraph boundaries for later LLM extraction.
6. Writes source references so every annotation can be traced back to the original text.

## What it deliberately does NOT do

- Does not rewrite, correct, summarize, translate, or normalize prose.
- Does not decide who is speaking.
- Does not extract canonical characters, scenes, events, or scenarios.
- Does not match recurring scenarios.
- Does not call an LLM.
- Does not claim that every quoted span is spoken dialogue. Quotation marks can also
  represent thoughts, titles, or quoted text; these remain candidates for later analysis.

The source `normalized.txt` and paragraph text are never modified.

## Expected input

Pass the directory created by the ingestion module, for example:

```text
processed/DOC_001/ingestion_v1/
├── metadata.json
├── normalized.txt
├── chapters.json
└── paragraphs.json
```

The reader accepts paragraph arrays either as a JSON list or under a `paragraphs` key.
It recognizes common field aliases (`paragraph_id`/`id`, `text`, `start_offset`,
`end_offset`, `chapter_id`).

## Install

From this module directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If you already have an active virtual environment for the main project, activate that
environment instead of creating another one.

## Run

```powershell
python -m novel_preprocessing.cli "..\..\..\processed\DOC_001\ingestion_v1" `
  --output-dir "..\..\..\processed_preprocessing" `
  --document-id DOC_001 `
  --version 1
```

Or:

```powershell
novel-preprocess "path/to/ingestion_v1" --output-dir "processed_preprocessing"
```

Output:

```text
processed_preprocessing/
└── DOC_001/
    └── preprocessing_v1/
        ├── preprocessing_metadata.json
        ├── paragraph_annotations.json
        ├── sentence_segments.json
        ├── dialogue_candidates.json
        ├── chunks.json
        └── preprocessing_report.json
```

The output directory is created with `exist_ok=False` to prevent accidental overwrite.
Use a new version/output directory for each run.

## Design notes

- Offsets are zero-based, half-open character offsets into `normalized.txt`.
- `local_start` and `local_end` are offsets relative to the paragraph text.
- `source_start` and `source_end` are offsets relative to the normalized document.
- If ingestion paragraph offsets are missing, local offsets remain available and
  source offsets are `null`; the pipeline does not invent provenance.
- Sentence segmentation is intentionally conservative. Abbreviations and stylistic
  fragments can cause imperfect boundaries; inspect the report and sample outputs.
- Chunk sizes use a rough character-based token estimate (`chars / 4`), not a tokenizer.
  This keeps the module provider-independent. Replace with a model tokenizer later if needed.
