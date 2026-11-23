from __future__ import annotations

from dataclasses import dataclass
from charset_normalizer import from_bytes

from .exceptions import EncodingDetectionError


@dataclass(frozen=True)
class DecodedText:
    text: str
    encoding: str
    source: str
    confidence: float | None
    had_utf8_bom: bool


class EncodingDetector:
    """Decode bytes with BOM checks, optional explicit encoding, then best-effort detection."""

    def decode(self, data: bytes, explicit_encoding: str | None = None) -> DecodedText:
        if not data:
            raise EncodingDetectionError("The input file is empty.")

        had_utf8_bom = data.startswith(b"\xef\xbb\xbf")

        if explicit_encoding:
            try:
                return DecodedText(
                    text=data.decode(explicit_encoding),
                    encoding=explicit_encoding,
                    source="explicit",
                    confidence=1.0,
                    had_utf8_bom=had_utf8_bom,
                )
            except (LookupError, UnicodeDecodeError) as exc:
                raise EncodingDetectionError(
                    f"Could not decode file using requested encoding "
                    f"{explicit_encoding!r}: {exc}"
                ) from exc

        # BOMs are authoritative and avoid heuristic misclassification.
        bom_encodings = (
            (b"\xef\xbb\xbf", "utf-8-sig"),
            (b"\xff\xfe", "utf-16"),
            (b"\xfe\xff", "utf-16"),
        )
        for bom, encoding in bom_encodings:
            if data.startswith(bom):
                try:
                    return DecodedText(
                        text=data.decode(encoding),
                        encoding=encoding,
                        source="bom",
                        confidence=1.0,
                        had_utf8_bom=had_utf8_bom,
                    )
                except UnicodeDecodeError as exc:
                    raise EncodingDetectionError(f"BOM detected but decoding failed: {exc}") from exc

        try:
            return DecodedText(
                text=data.decode("utf-8"),
                encoding="utf-8",
                source="strict_utf8",
                confidence=1.0,
                had_utf8_bom=False,
            )
        except UnicodeDecodeError:
            pass

        best = from_bytes(data).best()
        if best is None or best.encoding is None:
            raise EncodingDetectionError(
                "Encoding could not be determined. Supply an explicit encoding."
            )

        # charset-normalizer's coherence is not a calibrated probability.
        coherence = float(getattr(best, "percent_coherence", 0.0) or 0.0) / 100.0
        if coherence < 0.20:
            raise EncodingDetectionError(
                "Encoding detection confidence is too low. "
                "Supply an explicit encoding such as cp1252."
            )

        try:
            decoded = str(best)
        except Exception as exc:
            raise EncodingDetectionError(f"Detected encoding could not be decoded: {exc}") from exc

        return DecodedText(
            text=decoded,
            encoding=str(best.encoding),
            source="charset_normalizer",
            confidence=coherence,
            had_utf8_bom=False,
        )
