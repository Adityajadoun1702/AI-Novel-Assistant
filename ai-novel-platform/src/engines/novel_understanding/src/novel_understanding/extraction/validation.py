from pydantic import BaseModel

class EvidenceValidator:
    def validate(self, records, normalized_text, document_id, chunk_id):
        errors = []
        for rec in records:
            if rec.document_id != document_id or rec.chunk_id != chunk_id:
                errors.append("record document/chunk mismatch")
            for ev in rec.source_evidence:
                if ev.document_id != document_id or ev.chunk_id != chunk_id:
                    errors.append("evidence document/chunk mismatch")
                elif ev.end_offset > len(normalized_text):
                    errors.append("evidence offset out of bounds")
                elif normalized_text[ev.start_offset:ev.end_offset] != ev.exact_text:
                    errors.append("evidence text mismatch")
        return errors

class ReferenceValidator:
    def validate(self, records, known_entity_ids):
        errors = []
        for rec in records:
            refs = []
            if hasattr(rec, "participants"):
                refs += [p.entity_mention_id for p in rec.participants]
                refs += rec.object_mention_ids + rec.location_mention_ids
            if hasattr(rec, "source_entity_mention_id"):
                refs += [rec.source_entity_mention_id, rec.target_entity_mention_id]
            if hasattr(rec, "involved_entity_mention_ids"):
                refs += rec.involved_entity_mention_ids + rec.location_mention_ids
            errors += [f"unknown entity mention: {x}" for x in refs if x not in known_entity_ids]
        return errors
