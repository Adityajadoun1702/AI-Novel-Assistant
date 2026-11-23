from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required ingestion file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def unwrap_records(data: Any, preferred_key: str) -> list[dict]:
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get(preferred_key)
        if records is None:
            # Accept a few common wrappers without silently accepting arbitrary shapes.
            for key in ("items", "records", "data"):
                if isinstance(data.get(key), list):
                    records = data[key]
                    break
    else:
        records = None

    if not isinstance(records, list) or not all(isinstance(x, dict) for x in records):
        raise ValueError(f"Expected a JSON list or an object containing '{preferred_key}'")
    return records


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
