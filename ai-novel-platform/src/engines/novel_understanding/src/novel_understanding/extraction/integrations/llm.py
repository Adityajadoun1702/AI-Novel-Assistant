from typing import Protocol, TypeVar
from pydantic import BaseModel
T = TypeVar("T", bound=BaseModel)

class LLMAdapter(Protocol):
    provider: str
    model: str
    def generate_structured(self, *, system_prompt: str, user_prompt: str,
                            response_schema: type[T], temperature: float = 0.0) -> T: ...
