import argparse

from .entity_pipeline import EntityExtractionPipeline
from .integrations.mock_llm import MockLLMAdapter
from .integrations.ollama_adapter import OllamaAdapter


def main():
    parser = argparse.ArgumentParser(
        description="Extract entity mentions from preprocessed novel text."
    )
    parser.add_argument("--input-dir", required=True, help="Path to preprocessing_vN")
    parser.add_argument("--output-dir", help="Shared processed output directory")
    parser.add_argument("--document-id", help="Expected document ID")
    parser.add_argument("--version", type=int, default=2, help="Extraction version")
    parser.add_argument("--max-chunks", type=int, help="Optional development limit")
    parser.add_argument("--model", default="qwen3:4b", help="Local Ollama model")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama URL")
    parser.add_argument("--timeout", type=int, default=600, help="Ollama timeout in seconds")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Skip semantic extraction and write empty results for pipeline testing",
    )
    args = parser.parse_args()

    llm = MockLLMAdapter() if args.mock else OllamaAdapter(
        model=args.model,
        base_url=args.base_url,
        timeout=args.timeout,
        think=False,
    )
    result = EntityExtractionPipeline(llm).run(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        document_id=args.document_id,
        version=args.version,
        max_chunks=args.max_chunks,
    )
    print(result)
    return 0 if result["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
