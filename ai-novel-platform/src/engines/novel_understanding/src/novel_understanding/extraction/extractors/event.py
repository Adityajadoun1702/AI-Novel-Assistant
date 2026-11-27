from .base import BaseExtractor
from ..schemas.event import EventExtractionResponse
class EventExtractor(BaseExtractor):
    task = "event"
    prompt_version = "event_v1"
    def extract(self, chunk, entities):
        return self.call(chunk, EventExtractionResponse, {"entities": entities.model_dump()})
