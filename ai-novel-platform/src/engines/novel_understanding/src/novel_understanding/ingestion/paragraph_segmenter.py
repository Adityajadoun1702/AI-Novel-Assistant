from __future__ import annotations

import re
from .schemas import HeadingCandidate, ParagraphRecord


class ParagraphSegmenter:
    """Split blank-line blocks and explicit heading lines without assigning chapters."""

    def segment(self, text: str, document_id: str, version: int,
                candidates: list[HeadingCandidate]) -> list[ParagraphRecord]:
        blocks = self._find_blocks(text)
        split_blocks: list[tuple[int, int]] = []
        candidate_by_start = {c.start_offset: c for c in candidates}
        for start, end in blocks:
            cuts = [c for c in candidates if start <= c.start_offset < end]
            cursor = start
            for candidate in cuts:
                if candidate.start_offset > cursor:
                    before_end = candidate.start_offset
                    while before_end > cursor and text[before_end - 1].isspace():
                        before_end -= 1
                    if before_end > cursor:
                        split_blocks.append((cursor, before_end))
                heading_end = candidate.end_offset
                split_blocks.append((candidate.start_offset, heading_end))
                cursor = heading_end
                while cursor < end and text[cursor] in " \t\r\n":
                    cursor += 1
            if cursor < end:
                tail_end = end
                while tail_end > cursor and text[tail_end - 1].isspace():
                    tail_end -= 1
                if tail_end > cursor:
                    split_blocks.append((cursor, tail_end))
            elif not cuts:
                split_blocks.append((start, end))

        records: list[ParagraphRecord] = []
        candidate_by_start = {c.start_offset: c for c in candidates}
        for index, (start, end) in enumerate(split_blocks, start=1):
            candidate = candidate_by_start.get(start)
            line_start = text.count("\n", 0, start) + 1
            line_end = text.count("\n", 0, end) + 1
            records.append(ParagraphRecord(
                paragraph_id=f"{document_id}_V{version}_P{index:06d}",
                document_id=document_id,
                sequence_number=index,
                text=text[start:end],
                start_offset=start,
                end_offset=end,
                source_line_start=line_start,
                source_line_end=line_end,
                is_heading_candidate=candidate is not None,
                heading_candidate_id=candidate.candidate_id if candidate else None,
            ))
        return records

    @staticmethod
    def _find_blocks(text: str) -> list[tuple[int, int]]:
        blocks: list[tuple[int, int]] = []
        cursor = 0
        for match in re.finditer(r"(?m)^[ \t]*\n+", text):
            raw = text[cursor:match.start()]
            left = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            if raw.strip():
                blocks.append((cursor + left, cursor + right))
            cursor = match.end()
        raw = text[cursor:]
        if raw.strip():
            left = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            blocks.append((cursor + left, cursor + right))
        return blocks
