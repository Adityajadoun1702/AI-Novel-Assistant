"""Minimal OpenAI Responses API adapter using the Python standard library."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENTITY_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "segment_id": {"type": "string"},
                    "surface_text": {"type": "string"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["person", "place", "organization", "object", "animal", "group", "other"],
                    },
                    "mention_kind": {
                        "type": "string",
                        "enum": ["proper_name", "nominal_reference", "pronoun", "description", "unknown"],
                    },
                    "normalized_text": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                },
                "required": [
                    "segment_id", "surface_text", "entity_type", "mention_kind",
                    "normalized_text", "confidence",
                ],
            },
        }
    },
    "required": ["mentions"],
}


class OpenAIResponsesAdapter:
    provider = "openai"

    def __init__(self, api_key=None, model=None, base_url=None, timeout=120):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        if not self.model:
            raise ValueError("Set OPENAI_MODEL or pass model=...")

    def generate_structured(
        self, *, system_prompt, user_prompt, response_schema, temperature=0.0
    ):
        # This first implementation deliberately supports the entity response contract only.
        if response_schema.__name__ != "EntityCandidateResponse":
            raise NotImplementedError("This adapter currently supports entity extraction only")

        body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "entity_extraction",
                    "strict": True,
                    "schema": ENTITY_RESPONSE_SCHEMA,
                }
            },
        }
        request = Request(
            f"{self.base_url}/responses",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach OpenAI API: {exc.reason}") from exc

        output_text = payload.get("output_text")
        if not output_text:
            # Defensive extraction for responses that omit the convenience field.
            pieces = []
            for item in payload.get("output", []):
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            pieces.append(content.get("text", ""))
            output_text = "\n".join(pieces)
        if not output_text:
            raise RuntimeError(f"OpenAI response contained no output text: {payload}")
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI returned invalid JSON despite structured output") from exc
        return response_schema.model_validate(parsed)
