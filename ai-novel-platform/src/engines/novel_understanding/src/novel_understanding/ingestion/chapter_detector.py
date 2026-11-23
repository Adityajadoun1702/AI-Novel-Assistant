from __future__ import annotations

import re
from .schemas import HeadingCandidate


class HeadingCandidateDetector:
    """Find possible structural headings. It deliberately does NOT decide hierarchy."""

    VERSION = "heading-candidates-v2"
    _INDEX = r"(?:\d{1,4}|[ivxlcdm]{1,8}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    _RULES = [
        ("chapter", re.compile(r"^chapter\s+" + _INDEX + r"(?:\s*[:.\-–—].*)?$", re.I)),
        ("part", re.compile(r"^part\s+" + _INDEX + r"(?:\s*[:.\-–—].*)?$", re.I)),
        ("volume", re.compile(r"^volume\s+" + _INDEX + r"(?:\s*[:.\-–—].*)?$", re.I)),
        ("book", re.compile(r"^book\s+" + _INDEX + r"(?:\s*[:.\-–—].*)?$", re.I)),
        ("section", re.compile(r"^section\s+" + _INDEX + r"(?:\s*[:.\-–—].*)?$", re.I)),
        ("special_section", re.compile(r"^(?:prologue|epilogue|interlude|appendix)(?:\s*[:.\-–—].*)?$", re.I)),
    ]

    def detect(self, text: str, document_id: str, version: int) -> list[HeadingCandidate]:
        candidates: list[HeadingCandidate] = []
        offset = 0
        for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
            raw = line.rstrip("\r\n")
            content = raw.strip()
            if content:
                for role, pattern in self._RULES:
                    if pattern.fullmatch(content):
                        leading = len(raw) - len(raw.lstrip())
                        start = offset + leading
                        candidates.append(HeadingCandidate(
                            candidate_id=f"{document_id}_V{version}_HC{len(candidates)+1:04d}",
                            heading_text=content,
                            line_number=line_number,
                            start_offset=start,
                            end_offset=start + len(content),
                            role_hints=[role],
                            detector_version=self.VERSION,
                            evidence=[f"Matched explicit structural keyword: {role}"],
                        ))
                        break
            offset += len(line)
        return candidates
