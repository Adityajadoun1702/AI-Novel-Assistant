from __future__ import annotations

from collections import defaultdict

from .exceptions import SourceValidationError
from .schemas import HeadingCandidate, ParagraphRecord, StructureAnalysis


class IngestionValidator:
    """Validate source alignment and AI-produced document hierarchy."""

    def validate(
        self,
        normalized_text: str,
        candidates: list[HeadingCandidate],
        paragraphs: list[ParagraphRecord],
    ) -> None:
        candidate_by_id: dict[str, HeadingCandidate] = {}
        previous_candidate_start = -1

        for candidate in candidates:
            if candidate.candidate_id in candidate_by_id:
                raise SourceValidationError(f"Duplicate heading candidate ID: {candidate.candidate_id}")
            if not (0 <= candidate.start_offset < candidate.end_offset <= len(normalized_text)):
                raise SourceValidationError(f"Invalid heading candidate range: {candidate.candidate_id}")
            if normalized_text[candidate.start_offset:candidate.end_offset] != candidate.heading_text:
                raise SourceValidationError(f"Heading candidate offset mismatch: {candidate.candidate_id}")
            if candidate.start_offset < previous_candidate_start:
                raise SourceValidationError("Heading candidates are not in source order")
            previous_candidate_start = candidate.start_offset
            candidate_by_id[candidate.candidate_id] = candidate

        paragraph_ids: set[str] = set()
        previous_start = -1
        previous_end = -1
        seen_heading_candidates: set[str] = set()

        for expected_sequence, paragraph in enumerate(paragraphs, start=1):
            if paragraph.paragraph_id in paragraph_ids:
                raise SourceValidationError(f"Duplicate paragraph ID: {paragraph.paragraph_id}")
            paragraph_ids.add(paragraph.paragraph_id)
            if paragraph.sequence_number != expected_sequence:
                raise SourceValidationError("Paragraph sequence numbers must be contiguous and 1-based")
            if not (0 <= paragraph.start_offset < paragraph.end_offset <= len(normalized_text)):
                raise SourceValidationError(f"Invalid offsets for {paragraph.paragraph_id}")
            if normalized_text[paragraph.start_offset:paragraph.end_offset] != paragraph.text:
                raise SourceValidationError(f"Source offset mismatch for {paragraph.paragraph_id}")
            if paragraph.start_offset < previous_start or paragraph.start_offset < previous_end:
                raise SourceValidationError("Paragraphs are not in source order or overlap")
            if paragraph.source_line_start > paragraph.source_line_end:
                raise SourceValidationError(f"Invalid source line range for {paragraph.paragraph_id}")

            if paragraph.is_heading_candidate != (paragraph.heading_candidate_id is not None):
                raise SourceValidationError(
                    f"Heading flag and candidate reference disagree for {paragraph.paragraph_id}"
                )
            if paragraph.heading_candidate_id:
                candidate = candidate_by_id.get(paragraph.heading_candidate_id)
                if candidate is None:
                    raise SourceValidationError(f"Unknown heading candidate on {paragraph.paragraph_id}")
                if paragraph.start_offset != candidate.start_offset or paragraph.end_offset != candidate.end_offset:
                    raise SourceValidationError(
                        f"Heading paragraph range does not match candidate {candidate.candidate_id}"
                    )
                seen_heading_candidates.add(candidate.candidate_id)

            previous_start = paragraph.start_offset
            previous_end = paragraph.end_offset

        missing_heading_paragraphs = set(candidate_by_id) - seen_heading_candidates
        if missing_heading_paragraphs:
            raise SourceValidationError(
                "Heading candidates are not represented as heading paragraphs: "
                + ", ".join(sorted(missing_heading_paragraphs))
            )

    def validate_structure(
        self,
        normalized_text: str,
        analysis: StructureAnalysis,
        candidates: list[HeadingCandidate],
    ) -> None:
        if analysis.status != "completed":
            raise SourceValidationError("A supplied structure result must have status='completed'")

        candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
        classifications: dict[str, str] = {}
        uncertain_ids: set[str] = set()

        for item in analysis.candidate_classifications:
            if item.candidate_id in classifications:
                raise SourceValidationError(f"Candidate classified more than once: {item.candidate_id}")
            if item.candidate_id not in candidate_by_id:
                raise SourceValidationError(f"Classification references unknown candidate: {item.candidate_id}")
            classifications[item.candidate_id] = item.classification
            if item.classification == "uncertain":
                uncertain_ids.add(item.candidate_id)

        expected_candidate_ids = set(candidate_by_id)
        classified_candidate_ids = set(classifications)
        missing = expected_candidate_ids - classified_candidate_ids
        extra = classified_candidate_ids - expected_candidate_ids
        if missing or extra:
            details = []
            if missing:
                details.append("missing=" + ",".join(sorted(missing)))
            if extra:
                details.append("extra=" + ",".join(sorted(extra)))
            raise SourceValidationError("Candidate classifications must cover every candidate exactly once (" + "; ".join(details) + ")")

        unresolved_list = analysis.unresolved_candidate_ids
        if len(unresolved_list) != len(set(unresolved_list)):
            raise SourceValidationError("unresolved_candidate_ids contains duplicates")
        if set(unresolved_list) != uncertain_ids:
            raise SourceValidationError(
                "unresolved_candidate_ids must exactly match candidates classified as uncertain"
            )

        units_by_id = {}
        unit_by_candidate: dict[str, str] = {}
        for unit in analysis.units:
            if unit.unit_id in units_by_id:
                raise SourceValidationError(f"Duplicate structural unit ID: {unit.unit_id}")
            units_by_id[unit.unit_id] = unit
            if not (0 <= unit.start_offset < unit.end_offset <= len(normalized_text)):
                raise SourceValidationError(f"Invalid structural range: {unit.unit_id}")
            if unit.heading_candidate_id:
                if unit.heading_candidate_id not in candidate_by_id:
                    raise SourceValidationError(f"Unknown heading candidate: {unit.heading_candidate_id}")
                if unit.heading_candidate_id in unit_by_candidate:
                    raise SourceValidationError(
                        f"More than one structural unit references candidate {unit.heading_candidate_id}"
                    )
                unit_by_candidate[unit.heading_candidate_id] = unit.unit_id
                candidate = candidate_by_id[unit.heading_candidate_id]
                if unit.start_offset != candidate.start_offset:
                    raise SourceValidationError(
                        f"Unit {unit.unit_id} must start at its heading candidate offset "
                        f"({candidate.start_offset})"
                    )
                if unit.end_offset < candidate.end_offset:
                    raise SourceValidationError(f"Unit {unit.unit_id} ends before its heading ends")

                classification = classifications[unit.heading_candidate_id]
                if classification in {"not_a_heading", "uncertain"}:
                    raise SourceValidationError(
                        f"Unit {unit.unit_id} references candidate classified as {classification}"
                    )
                if classification != unit.unit_type:
                    raise SourceValidationError(
                        f"Unit type mismatch for candidate {unit.heading_candidate_id}: "
                        f"classification={classification}, unit_type={unit.unit_type}"
                    )

        # Every positively classified heading must map to one unit; negative/uncertain
        # classifications must not map to a unit.
        structural_classifications = {
            candidate_id: classification
            for candidate_id, classification in classifications.items()
            if classification not in {"not_a_heading", "uncertain"}
        }
        for candidate_id, classification in structural_classifications.items():
            if candidate_id not in unit_by_candidate:
                raise SourceValidationError(
                    f"Candidate {candidate_id} classified as {classification} has no structural unit"
                )
        for candidate_id in classifications:
            if classifications[candidate_id] in {"not_a_heading", "uncertain"} and candidate_id in unit_by_candidate:
                raise SourceValidationError(
                    f"Candidate {candidate_id} is classified as non-structural but has a unit"
                )

        # Validate parent references and containment.
        for unit in analysis.units:
            if unit.parent_unit_id:
                parent = units_by_id.get(unit.parent_unit_id)
                if parent is None:
                    raise SourceValidationError(f"Unknown parent unit: {unit.parent_unit_id}")
                if parent.unit_id == unit.unit_id:
                    raise SourceValidationError(f"Unit cannot be its own parent: {unit.unit_id}")
                if not (parent.start_offset <= unit.start_offset and unit.end_offset <= parent.end_offset):
                    raise SourceValidationError(
                        f"Parent range does not contain child range: {parent.unit_id} -> {unit.unit_id}"
                    )

        # Detect cycles after checking that all parent references exist.
        for unit in analysis.units:
            visited = {unit.unit_id}
            parent_id = unit.parent_unit_id
            while parent_id is not None:
                if parent_id in visited:
                    raise SourceValidationError("Structural hierarchy contains a cycle")
                visited.add(parent_id)
                parent_id = units_by_id[parent_id].parent_unit_id

        # Order is sibling-local, 1-based, and must agree with source order.
        siblings: dict[str | None, list] = defaultdict(list)
        for unit in analysis.units:
            siblings[unit.parent_unit_id].append(unit)

        for parent_id, group in siblings.items():
            ordered = sorted(group, key=lambda item: item.order)
            expected_orders = list(range(1, len(ordered) + 1))
            actual_orders = [item.order for item in ordered]
            if actual_orders != expected_orders:
                label = parent_id or "<root>"
                raise SourceValidationError(
                    f"Sibling order under {label} must be contiguous and start at 1; got {actual_orders}"
                )
            previous = None
            for unit in ordered:
                if previous is not None:
                    if unit.start_offset < previous.start_offset:
                        raise SourceValidationError("Sibling order conflicts with source order")
                    if unit.start_offset < previous.end_offset:
                        raise SourceValidationError(
                            f"Sibling structural ranges overlap: {previous.unit_id} and {unit.unit_id}"
                        )
                previous = unit
