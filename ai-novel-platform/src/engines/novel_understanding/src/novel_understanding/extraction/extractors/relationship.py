from .base import BaseExtractor
from ..schemas.relationship import RelationshipExtractionResponse
class RelationshipExtractor(BaseExtractor):
    task = "relationship"
    prompt_version = "relationship_v1"
    def extract(self, chunk, entities, events):
        return self.call(chunk, RelationshipExtractionResponse, {
            "entities": entities.model_dump(), "events": events.model_dump()
        })
