from pathlib import Path
import json

class BaseExtractor:
    task = "base"
    prompt_version = "base_v1"
    def __init__(self, llm, prompt_dir=None):
        self.llm = llm
        self.prompt_dir = Path(prompt_dir) if prompt_dir else Path(__file__).parents[1] / "prompts"
    def call(self, chunk, schema, context):
        prompt = (self.prompt_dir / f"{self.task}.md").read_text(encoding="utf-8")
        user = f"CHUNK_ID: {chunk.chunk_id}\\nCHUNK_TEXT:\\n{chunk.text}\\nCONTEXT:\\n{json.dumps(context, ensure_ascii=False)}"
        return self.llm.generate_structured(system_prompt=prompt, user_prompt=user,
                                            response_schema=schema, temperature=0.0)
