class TextNormalizer:
    """Only normalize line endings; preserve all other decoded characters."""

    VERSION = "1.0"

    def normalize(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")
