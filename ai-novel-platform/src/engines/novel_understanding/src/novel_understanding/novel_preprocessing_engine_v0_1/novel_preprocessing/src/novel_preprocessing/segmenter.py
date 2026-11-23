from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalSpan:
    start: int
    end: int
    text: str


_ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.",
    "vs.", "etc.", "e.g.", "i.e.", "no.", "fig.", "vol.",
}


def split_sentences(text: str) -> list[LocalSpan]:
    """Split on likely sentence-ending punctuation, preserving exact text spans.

    This is a pragmatic baseline, not a linguistic parser. It avoids common abbreviations,
    decimal points, and punctuation inside paired quotation marks where possible.
    """
    if not text:
        return []

    spans: list[LocalSpan] = []
    start = 0
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if ch not in ".!?。！？":
            i += 1
            continue

        # Do not split decimal numbers.
        if ch == "." and i > 0 and i + 1 < n and text[i - 1].isdigit() and text[i + 1].isdigit():
            i += 1
            continue

        # Common abbreviation check.
        if ch == ".":
            left = text[max(start, i - 12):i + 1].lower()
            token_match = re.search(r"(?:[a-z]+\.)$", left)
            if token_match and token_match.group(0) in _ABBREVIATIONS:
                i += 1
                continue

        # Include closing quotes/brackets after terminal punctuation.
        end = i + 1
        while end < n and text[end] in "\"'”’」』】)":
            end += 1

        # A sentence boundary is likely before whitespace or at paragraph end.
        if end == n or text[end].isspace():
            raw = text[start:end]
            left_trim = len(raw) - len(raw.lstrip())
            right_trimmed = len(raw.rstrip())
            actual_start = start + left_trim
            actual_end = start + right_trimmed
            if actual_start < actual_end:
                spans.append(LocalSpan(actual_start, actual_end, text[actual_start:actual_end]))
            start = end
            while start < n and text[start].isspace():
                start += 1
            i = start
        else:
            i += 1

    if start < n:
        raw = text[start:]
        left_trim = len(raw) - len(raw.lstrip())
        actual_start = start + left_trim
        actual_end = len(text.rstrip())
        if actual_start < actual_end:
            spans.append(LocalSpan(actual_start, actual_end, text[actual_start:actual_end]))

    # Fallback for text with no terminal punctuation.
    if not spans and text.strip():
        a = len(text) - len(text.lstrip())
        b = len(text.rstrip())
        spans.append(LocalSpan(a, b, text[a:b]))

    return spans
