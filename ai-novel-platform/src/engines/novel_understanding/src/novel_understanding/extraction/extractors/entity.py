from .base import BaseExtractor
from ..schemas.entity import EntityExtractionResponse
class EntityExtractor(BaseExtractor):
    task = "entity"
    prompt_version = "entity_v1"
    def extract(self, chunk, candidates):
        return self.call(chunk, EntityExtractionResponse, {"candidates": candidates.model_dump()})
