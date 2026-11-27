"""Local Ollama adapter using the Ollama /api/chat endpoint."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaAdapter:
    """Generate Pydantic-validated structured output from a local Ollama model."""

    provider = "ollama"

    def __init__(
        self,
        model: str = "qwen3:4b",
        base_url: str = "http://localhost:11434",
        timeout: int = 600,
        think: bool = False,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.think = think

    def generate_structured(
        self, *, system_prompt, user_prompt, response_schema, temperature=0.0
    ):
        schema = response_schema.model_json_schema()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": self.think,
            "format": schema,
            "options": {"temperature": temperature},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. "
                "Check that Ollama is running. "
                f"Underlying error: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout} seconds"
            ) from exc

        message = payload.get("message") or {}
        output_text = message.get("content")
        if not output_text:
            raise RuntimeError(
                f"Ollama response contained no message.content: {payload}"
            )
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON despite structured output mode"
            ) from exc
        try:
            return response_schema.model_validate(parsed)
        except Exception as exc:
            raise RuntimeError(
                f"Ollama JSON did not match {response_schema.__name__}: {exc}"
            ) from exc
