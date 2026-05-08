import os
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from core.chunker import read_chunk, get_chunk_count, chunk_hash


class FileServer:
    def __init__(self):
        self.files: list[str] = []
        self.port: int = 8765
        self.bytes_sent: int = 0
        self.active_connections: int = 0
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self.app = self._build_app()

    def set_files(self, paths: list[str]) -> None:
        self.files = list(paths)
        self.bytes_sent = 0

    def set_file(self, path: str) -> None:
        self.set_files([path])

    @property
    def file_path(self) -> Optional[str]:
        return self.files[0] if self.files else None

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/files")
        def get_files():
            result = []
            for i, path in enumerate(self.files):
                if not os.path.exists(path):
                    continue
                size = os.path.getsize(path)
                result.append({
                    "index": i,
                    "file_name": os.path.basename(path),
                    "file_size": size,
                    "total_chunks": get_chunk_count(size),
                })
            return result

        @app.get("/info")
        def get_info():
            if not self.files or not os.path.exists(self.files[0]):
                raise HTTPException(status_code=404, detail="No file available")
            path = self.files[0]
            size = os.path.getsize(path)
            return {
                "file_name": os.path.basename(path),
                "file_size": size,
                "total_chunks": get_chunk_count(size),
            }

        @app.get("/file/{index}/info")
        def get_file_info(index: int):
            if index < 0 or index >= len(self.files):
                raise HTTPException(status_code=404, detail="File not found")
            path = self.files[index]
            if not os.path.exists(path):
                raise HTTPException(status_code=404, detail="File not found")
            size = os.path.getsize(path)
            return {
                "index": index,
                "file_name": os.path.basename(path),
                "file_size": size,
                "total_chunks": get_chunk_count(size),
            }

        @app.get("/file/{index}/chunk/{chunk_index}")
        def get_file_chunk(index: int, chunk_index: int):
            if index < 0 or index >= len(self.files):
                raise HTTPException(status_code=404)
            path = self.files[index]
            size = os.path.getsize(path)
            count = get_chunk_count(size)
            if chunk_index < 0 or chunk_index >= count:
                raise HTTPException(status_code=400, detail="Invalid chunk index")
            data = read_chunk(path, chunk_index)
            h = chunk_hash(data)
            self.bytes_sent += len(data)
            return Response(
                content=data,
                media_type="application/octet-stream",
                headers={"X-Chunk-Hash": h},
            )

        @app.get("/chunk/{index}")
        def get_chunk(index: int):
            if not self.files:
                raise HTTPException(status_code=404)
            path = self.files[0]
            size = os.path.getsize(path)
            count = get_chunk_count(size)
            if index < 0 or index >= count:
                raise HTTPException(status_code=400, detail="Invalid chunk index")
            data = read_chunk(path, index)
            h = chunk_hash(data)
            self.bytes_sent += len(data)
            return Response(
                content=data,
                media_type="application/octet-stream",
                headers={"X-Chunk-Hash": h},
            )

        @app.get("/ping")
        def ping():
            return {"status": "ok"}

        return app

    def start(self) -> None:
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="error",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        def run():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._server.serve())

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        self.files = []
        self.bytes_sent = 0


file_server = FileServer()
