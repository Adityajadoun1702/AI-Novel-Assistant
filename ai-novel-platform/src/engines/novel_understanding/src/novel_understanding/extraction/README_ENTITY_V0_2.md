# Entity Extraction v0.2

This is an entity-only implementation for the AI Novel Assistant extraction stage.
It reads the actual project layout:

```text
processed/DOC_ID/
├── ingestion_vN/
│   ├── metadata.json
│   ├── normalized.txt
│   └── paragraphs.json
└── preprocessing_vN/
    ├── preprocessing_metadata.json
    ├── chunks.json
    ├── sentence_segments.json
    └── dialogue_candidates.json
```

## What it extracts

It extracts entity *mentions* from each chunk: people, places, organizations,
objects, animals, groups, and other references. It does not resolve mentions to
canonical characters/entities. It does not extract events, relationships, or
narrative context.

The model returns only semantic fields plus a segment ID and exact surface text.
It does not return occurrence indices: Python expands each exact surface to every
matching occurrence in that segment, then generates mention IDs, resolves offsets
against normalized source text, creates provenance/evidence records, validates
the exact source slice, and writes JSON output. Unsupported model candidates are
skipped with warnings in the chunk manifest instead of discarding other valid
mentions from that chunk.

## Install

From the directory containing the existing project `pyproject.toml`:

```powershell
python -m pip install -e ".[dev]"
```

No new project-level `pyproject.toml` is included in this patch. The OpenAI adapter
uses Python's standard library for HTTP and does not add an SDK dependency.

## Configure OpenAI

PowerShell (current terminal session):

```powershell
$env:OPENAI_API_KEY = "YOUR_API_KEY"
$env:OPENAI_MODEL = "YOUR_SUPPORTED_MODEL"
```

Do not commit the key or put it in source code. `OPENAI_MODEL` must be a model
available to the API project associated with that key.

## Run one chunk first

```powershell
python -m novel_understanding.extraction.entity_cli `
  --input-dir ".\processed\DOC_REAL_001\preprocessing_v2" `
  --output-dir ".\processed" `
  --document-id DOC_REAL_001 `
  --version 2 `
  --max-chunks 1
```

## Run all chunks

After reviewing the first chunk's results:

```powershell
python -m novel_understanding.extraction.entity_cli `
  --input-dir ".\processed\DOC_REAL_001\preprocessing_v2" `
  --output-dir ".\processed" `
  --document-id DOC_REAL_001 `
  --version 2
```

Output:

```text
processed/DOC_REAL_001/extraction_v2/
├── entities/
│   ├── CHK_000001.json
│   └── ...
├── manifest.json
├── metadata.json
└── extraction_report.json
```

A failed chunk is marked failed in the manifest/report. Existing output versions are
never overwritten; use `--version 3` for a new run.

## Test

```powershell
python -m pytest tests/extraction -v
```

To run the integration test against the supplied document, set
`ENTITY_FIXTURE_ROOT` to the actual `preprocessing_v2` folder first.

## Important limits

- LLM extraction is probabilistic; validate results before downstream use.
- Entity mentions are not canonical characters.
- Pronoun resolution and coreference are not performed.
- Evidence is anchored to one sentence segment per mention.
- The OpenAI adapter currently supports the entity response schema only.
- This version does not yet run event, relationship, or narrative-context extraction.
