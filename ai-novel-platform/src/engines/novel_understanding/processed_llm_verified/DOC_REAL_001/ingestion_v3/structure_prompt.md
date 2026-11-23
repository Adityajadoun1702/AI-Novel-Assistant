You are analyzing the DOCUMENT STRUCTURE of a novel. Do not summarize, rewrite, or continue the novel.

Return one JSON object only. Do not include Markdown fences or explanatory text outside the JSON.

TASK
1. Classify EVERY supplied heading candidate exactly once.
2. A candidate classification must be one of:
   volume, book, chapter, part, section, subsection, prologue, epilogue,
   interlude, appendix, other, not_a_heading, uncertain.
3. `not_a_heading` means the candidate is ordinary text and must not create a structural unit.
4. `uncertain` means the supplied evidence is insufficient. Put its candidate_id in unresolved_candidate_ids.
5. Create structural units only for candidates classified as a structural type. Do not create a unit for not_a_heading or uncertain.
6. Infer parent-child hierarchy from the whole supplied document. A Part inside a Chapter is a child of that Chapter; it is not another Chapter. Do not assume every numbered heading is a chapter.
7. Do not invent headings, chapter numbers, parts, or missing content. Units without an explicit heading candidate should be rare and must be justified by the source text.

RANGE AND ORDER RULES
- All offsets are zero-based character offsets into normalized_text; ranges are half-open [start_offset, end_offset).
- If a unit has heading_candidate_id, its start_offset MUST equal that candidate's start_offset. Its end_offset must be after the heading and no later than the end of its content.
- A parent unit's range must contain the full range of every direct or indirect child.
- Sibling units (units with the same parent_unit_id, including root units) must not overlap.
- `order` is 1-based among siblings with the same parent and must follow source order.
- Use exact candidate IDs and offsets. Never estimate or renumber IDs.
- Each candidate must appear exactly once in candidate_classifications.
- Every structural classification must have exactly one matching unit whose unit_type equals the classification.
- `unresolved_candidate_ids` must contain exactly the candidates classified as uncertain, and no others.

OUTPUT SHAPE
{
  "analyzer": "provider/model identifier",
  "candidate_classifications": [
    {
      "candidate_id": "exact supplied candidate ID",
      "classification": "chapter",
      "confidence": 0.98,
      "rationale": "Brief explanation grounded in the supplied document"
    }
  ],
  "units": [
    {
      "unit_id": "stable document-scoped ID",
      "unit_type": "chapter",
      "title": "Chapter 1: Example",
      "heading_candidate_id": "exact candidate ID or null",
      "parent_unit_id": null,
      "order": 1,
      "start_offset": 0,
      "end_offset": 100,
      "confidence": 0.95,
      "rationale": "Brief evidence-based explanation"
    }
  ],
  "unresolved_candidate_ids": []
}

Do not return fields outside this shape. Do not use `not_a_heading` as a unit_type.
