class IngestionError(Exception):
    """Base exception for ingestion failures."""


class UnsupportedFileTypeError(IngestionError):
    pass


class EmptyDocumentError(IngestionError):
    pass


class EncodingDetectionError(IngestionError):
    pass


class FileSizeLimitError(IngestionError):
    pass


class SourceValidationError(IngestionError):
    pass
