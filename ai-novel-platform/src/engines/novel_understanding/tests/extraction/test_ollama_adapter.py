import json

from novel_understanding.extraction.integrations import ollama_adapter
from novel_understanding.extraction.integrations.ollama_adapter import OllamaAdapter
from novel_understanding.extraction.schemas.entity import EntityCandidateResponse


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_adapter_sends_schema_and_validates_response(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse({
            "message": {
                "role": "assistant",
                "content": json.dumps({
                    "mentions": [{
                        "segment_id": "SEG_1",
                        "surface_text": "Arjun",
                        "entity_type": "person",
                        "mention_kind": "proper_name",
                        "normalized_text": "Arjun",
                        "confidence": 0.95,
                    }]
                })
            }
        })

    monkeypatch.setattr(ollama_adapter, "urlopen", fake_urlopen)
    adapter = OllamaAdapter()

    result = adapter.generate_structured(
        system_prompt="Extract entities.",
        user_prompt='{"segments":[]}',
        response_schema=EntityCandidateResponse,
        temperature=0.0,
    )

    assert result.mentions[0].surface_text == "Arjun"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["body"]["model"] == "qwen3:4b"
    assert captured["body"]["think"] is False
    assert captured["body"]["stream"] is False
    assert captured["body"]["options"]["temperature"] == 0.0
    assert captured["body"]["format"]["type"] == "object"
    assert "occurrence_index" not in captured["body"]["format"]["$defs"]["EntityCandidate"]["properties"]
    assert captured["timeout"] == 600


def test_ollama_adapter_rejects_invalid_json(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({"message": {"content": "not json"}})

    monkeypatch.setattr(ollama_adapter, "urlopen", fake_urlopen)
    adapter = OllamaAdapter()

    try:
        adapter.generate_structured(
            system_prompt="x",
            user_prompt="y",
            response_schema=EntityCandidateResponse,
        )
    except RuntimeError as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("Expected invalid JSON to raise RuntimeError")
