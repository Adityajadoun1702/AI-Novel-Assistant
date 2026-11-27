from .base import BaseExtractor
from ..schemas.context import ContextExtractionResponse
class ContextExtractor(BaseExtractor):
    task = "context"
    prompt_version = "context_v1"
    def extract(self, chunk, entities, events, relationships):
        return self.call(chunk, ContextExtractionResponse, {
            "entities": entities.model_dump(), "events": events.model_dump(),
            "relationships": relationships.model_dump()
        })
