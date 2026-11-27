import re
from pydantic import BaseModel, Field

class Candidate(BaseModel):
    text: str
    kind: str

class CandidateResult(BaseModel):
    candidates: list[Candidate] = Field(default_factory=list)

class CandidateDetector:
    PRONOUNS = {"he","she","they","him","her","them","his","hers","their","i","we","you","me","us","it"}
    def detect(self, text):
        found = {}
        for m in re.finditer(r"\b[A-Z][a-zA-Z'-]*(?:\s+[A-Z][a-zA-Z'-]*)*\b", text):
            found[(m.group(), "proper_name")] = Candidate(text=m.group(), kind="proper_name")
        for m in re.finditer(r"\b[A-Za-z']+\b", text):
            if m.group().lower() in self.PRONOUNS:
                found[(m.group(), "pronoun")] = Candidate(text=m.group(), kind="pronoun")
        return CandidateResult(candidates=list(found.values()))
