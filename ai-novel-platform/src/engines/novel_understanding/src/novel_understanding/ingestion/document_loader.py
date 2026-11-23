from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .exceptions import EmptyDocumentError, FileSizeLimitError, UnsupportedFileTypeError


@dataclass(frozen=True)
class LoadedFile:
    path: Path
    file_name: str
    data: bytes


class DocumentLoader:
    def __init__(self, max_file_size_bytes: int = 50 * 1024 * 1024):
        self.max_file_size_bytes = max_file_size_bytes

    def load(self, file_path: str | Path) -> LoadedFile:
        path = Path(file_path)
        if path.suffix.lower() != ".txt":
            raise UnsupportedFileTypeError(
                f"Only .txt files are supported in Phase 1; received {path.suffix or 'no extension'}."
            )
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {path}")
        size = path.stat().st_size
        if size > self.max_file_size_bytes:
            raise FileSizeLimitError(
                f"File is {size} bytes; configured maximum is {self.max_file_size_bytes} bytes."
            )
        data = path.read_bytes()
        if not data:
            raise EmptyDocumentError("The TXT file is empty.")
        return LoadedFile(path=path, file_name=path.name, data=data)
