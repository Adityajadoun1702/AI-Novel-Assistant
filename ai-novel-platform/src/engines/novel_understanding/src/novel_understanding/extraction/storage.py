import json, os
from pathlib import Path
class JsonStore:
    def write(self, path, data):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        with tmp.open("rb") as f: os.fsync(f.fileno())
        os.replace(tmp, p)
