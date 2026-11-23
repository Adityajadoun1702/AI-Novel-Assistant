from __future__ import annotations

from dataclasses import dataclass


PAIRS = {
    '"': '"',
    "“": "”",
    "「": "」",
    "『": "』",
    "‘": "’",
}


@dataclass(frozen=True)
class QuoteSpan:
    start: int
    end: int
    text: str
    quote_style: str


def find_quoted_spans(text: str) -> list[QuoteSpan]:
    """Find balanced quoted spans. Apostrophes inside words are ignored."""
    found: list[QuoteSpan] = []
    i = 0
    while i < len(text):
        opener = text[i]
        closer = PAIRS.get(opener)
        if closer is None:
            i += 1
            continue
        if opener == "'" and i > 0 and i + 1 < len(text) and text[i - 1].isalnum() and text[i + 1].isalnum():
            i += 1
            continue

        j = i + 1
        while j < len(text):
            if text[j] == closer:
                # For straight quotes, avoid treating a quote in a contraction as a close.
                found.append(QuoteSpan(i, j + 1, text[i:j + 1], opener))
                i = j + 1
                break
            j += 1
        else:
            i += 1
    return found
