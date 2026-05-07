import hashlib
import os

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def get_chunk_count(file_size: int) -> int:
    return max(1, (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE)


def get_chunk_offset(chunk_index: int) -> int:
    return chunk_index * CHUNK_SIZE


def read_chunk(file_path: str, chunk_index: int) -> bytes:
    with open(file_path, "rb") as f:
        f.seek(get_chunk_offset(chunk_index))
        return f.read(CHUNK_SIZE)


def chunk_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"
