from .encoding_detector import EncodingDetector, DecodedText


class TXTExtractor:
    def __init__(self, encoding_detector: EncodingDetector | None = None):
        self.encoding_detector = encoding_detector or EncodingDetector()

    def extract(self, data: bytes, explicit_encoding: str | None = None) -> DecodedText:
        return self.encoding_detector.decode(data, explicit_encoding)
