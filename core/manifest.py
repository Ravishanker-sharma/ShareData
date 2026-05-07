import json
import os
from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class Manifest:
    file_name: str
    file_size: int
    total_chunks: int
    save_path: str
    tunnel_url: str
    completed_chunks: List[int] = field(default_factory=list)

    def is_complete(self) -> bool:
        return len(self.completed_chunks) == self.total_chunks

    def pending_chunks(self) -> List[int]:
        done = set(self.completed_chunks)
        return [i for i in range(self.total_chunks) if i not in done]

    def progress_fraction(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return len(self.completed_chunks) / self.total_chunks

    def bytes_done(self) -> int:
        from core.chunker import CHUNK_SIZE
        full_chunks = len(self.completed_chunks)
        # Last chunk may be smaller — approximate with CHUNK_SIZE
        return full_chunks * CHUNK_SIZE


def manifest_path(save_path: str) -> str:
    return save_path + ".sharedata"


def save_manifest(manifest: Manifest, path: str) -> None:
    with open(path, "w") as f:
        json.dump(asdict(manifest), f)


def load_manifest(path: str) -> Optional[Manifest]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return Manifest(**data)
    except Exception:
        return None
