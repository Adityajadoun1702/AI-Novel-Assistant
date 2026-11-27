from __future__ import annotations

import re
from dataclasses import dataclass
from .schemas import SpanType


@dataclass(frozen=True)
class Classification:
    label: SpanType
    method: str
    confidence: float


FOOTNOTE_RE = re.compile(r"^\s*(?:\[\d+\]|\(\d+\)|\*\d*|†|‡)\s*")

# These are deliberately narrow, provisional cues. First-person narration alone
# is not enough to classify a sentence as an internal thought.
THOUGHT_CUES = (
    " i thought", " i wondered", " i asked myself", " i told myself",
    " i couldn't help thinking", " i could not help thinking",
    " i realized", " i realised", " i remembered",
    " i wanted to", " i didn't want to", " i did not want to",
    " i couldn't believe", " i could not believe",
    " i kept repeating", " in my mind", " i was scared",
)


def classify_paragraph(
    text: str,
    is_heading: bool = False,
    is_heading_candidate: bool = False,
) -> Classification:
    stripped = text.strip()
    if is_heading:
        return Classification("heading", "ingestion_confirmed_heading", 0.99)
    if is_heading_candidate:
        # Candidate is not proof. Keep the classification explicitly provisional.
        return Classification("heading", "ingestion_heading_candidate", 0.78)
    if FOOTNOTE_RE.match(stripped):
        return Classification("footnote", "footnote_pattern", 0.72)
    if not stripped:
        return Classification("unknown", "empty_text", 1.0)
    if _looks_like_dialogue_only(stripped):
        return Classification("dialogue", "quote_dominant_heuristic", 0.68)

    # Paragraphs can mix narration and thought. Do not label an entire long
    # paragraph as internal thought merely because one sentence contains "I".
    return Classification("narration", "default_paragraph_heuristic", 0.55)


def classify_segment(text: str, is_dialogue: bool = False) -> Classification:
    if is_dialogue:
        return Classification("dialogue", "contained_in_quoted_span", 0.82)
    if FOOTNOTE_RE.match(text.strip()):
        return Classification("footnote", "footnote_pattern", 0.72)

    lowered = f" {text.lower()} "
    if any(cue in lowered for cue in THOUGHT_CUES):
        return Classification("internal_thought", "first_person_thought_cue", 0.56)

    return Classification("narration", "default_segment_heuristic", 0.52)


def _looks_like_dialogue_only(text: str) -> bool:
    pairs = [('“', '”'), ('"', '"'), ('「', '」'), ('『', '』')]
    for opening, closing in pairs:
        if text.startswith(opening) and text.endswith(closing) and len(text) >= 2:
            return True
    return False
