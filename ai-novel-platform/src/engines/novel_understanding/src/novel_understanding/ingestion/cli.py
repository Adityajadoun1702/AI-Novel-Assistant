from __future__ import annotations

import argparse
from .pipeline import IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TXT and prepare hierarchical structure analysis.")
    parser.add_argument("file", help="Path to the .txt novel")
    parser.add_argument("--output-dir", default="processed")
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--encoding", default=None, help="Explicit encoding, e.g. cp1252")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--structure-result", default=None, help="Optional JSON result from a structure analyzer")
    args = parser.parse_args()
    pipeline = IngestionPipeline()
    result = pipeline.process(args.file, document_id=args.document_id,
        ingestion_version=args.version, encoding=args.encoding,
        structure_result=args.structure_result)
    output = pipeline.save(result, args.output_dir)
    print(f"Ingestion completed: {output}")
    print(f"Paragraphs: {len(result.paragraphs)} | Heading candidates: {len(result.heading_candidates)}")
    print(f"Structure analysis: {result.structure_analysis.status}")
    print(f"Source validation: {'PASS' if result.report.source_validation_passed else 'FAIL'}")
    structure_status = result.report.structure_validation_passed
    print("Structural validation: " + ("PASS" if structure_status is True else "NOT RUN" if structure_status is None else "FAIL"))
    print("Next: inspect structure_request.json and structure_prompt.md.")
    for warning in result.report.warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
