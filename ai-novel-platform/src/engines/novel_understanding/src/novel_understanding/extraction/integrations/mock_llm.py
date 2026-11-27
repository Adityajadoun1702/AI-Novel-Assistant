from pydantic import BaseModel

class MockLLMAdapter:
    provider = "mock"
    model = "mock-empty"

    def generate_structured(
        self, *, system_prompt, user_prompt, response_schema, temperature=0.0
    ):
        return response_schema()