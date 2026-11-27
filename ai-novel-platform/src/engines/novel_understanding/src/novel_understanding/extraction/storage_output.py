from pathlib import Path
from .storage import JsonStore

class OutputWriter:
    def __init__(self): self.store = JsonStore()
    def write_task(self, root, category, chunk_id, task, response):
        path = Path(root) / category / f"{chunk_id}.json"
        self.store.write(path, {"task": task, "chunk_id": chunk_id,
            "status": "completed", "records": [x.model_dump(mode="json") for x in response.records],
            "record_count": len(response.records)})
        return str(path)
