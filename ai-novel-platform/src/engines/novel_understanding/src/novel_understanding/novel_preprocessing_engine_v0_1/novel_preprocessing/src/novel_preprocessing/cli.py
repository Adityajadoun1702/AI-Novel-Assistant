from __future__ import annotations

import argparse
import json
import sys

from .pipeline import PreprocessingPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preprocess ingestion output for narrative extraction."
    )
    parser.add_argument(
        "ingestion_dir",
        help="Directory containing paragraphs.json from TXT ingestion",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output root. Defaults to the shared processed directory.",
    )
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--max-chunk-tokens", type=int, default=700)
    parser.add_argument("--overlap-segments", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        pipeline = PreprocessingPipeline(
            args.max_chunk_tokens, args.overlap_segments
        )
        result = pipeline.run(
            ingestion_dir=args.ingestion_dir,
            output_dir=args.output_dir,
            document_id=args.document_id,
            version=args.version,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["report"]["validation_passed"] else 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
