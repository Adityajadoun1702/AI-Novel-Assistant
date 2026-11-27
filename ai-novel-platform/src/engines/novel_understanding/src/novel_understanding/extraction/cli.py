import argparse
from .integrations.mock_llm import MockLLMAdapter
from .pipeline import ExtractionPipeline

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--output-dir")
    p.add_argument("--document-id", required=True)
    p.add_argument("--version", type=int, default=1)
    p.add_argument("--max-chunks", type=int)
    p.add_argument("--mock", action="store_true")
    args = p.parse_args()
    if not args.mock:
        raise SystemExit("No real provider adapter configured. Use --mock for pipeline testing.")
    result = ExtractionPipeline(MockLLMAdapter()).run(
        args.input_dir, args.output_dir, args.document_id, args.version, args.max_chunks)
    print(result)

if __name__ == "__main__": main()
