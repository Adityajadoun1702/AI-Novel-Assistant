class EvidenceValidator:
    def validate(self, records, normalized_text, document_id, chunk_id):
        errors = []
        for record in records:
            if record.document_id != document_id or record.chunk_id != chunk_id:
                errors.append("record document/chunk mismatch")
            for evidence in record.source_evidence:
                if evidence.document_id != document_id or evidence.chunk_id != chunk_id:
                    errors.append("evidence document/chunk mismatch")
                elif evidence.end_offset > len(normalized_text):
                    errors.append("evidence offset out of bounds")
                elif normalized_text[evidence.start_offset:evidence.end_offset] != evidence.exact_text:
                    errors.append("evidence text mismatch")
        return errors


class ReferenceValidator:
    def validate(self, records, known_entity_ids):
        errors = []
        for record in records:
            refs = []
            if hasattr(record, "participants"):
                refs += [p.entity_mention_id for p in record.participants]
                refs += record.object_mention_ids + record.location_mention_ids
            if hasattr(record, "source_entity_mention_id"):
                refs += [record.source_entity_mention_id, record.target_entity_mention_id]
            if hasattr(record, "involved_entity_mention_ids"):
                refs += record.involved_entity_mention_ids + record.location_mention_ids
            errors += [f"unknown entity mention: {value}" for value in refs if value not in known_entity_ids]
        return errors
