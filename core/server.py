import os
import threading
from typing import Optional, Callable

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from core.chunker import read_chunk, get_chunk_count, chunk_hash


class FileServer:
    def __init__(self):
        self.file_path: Optional[str] = None
        self.port: int = 8765
        self.bytes_sent: int = 0
        self.active_connections: int = 0
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self.app = self._build_app()

    def set_file(self, path: str) -> None:
        self.file_path = path
        self.bytes_sent = 0

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/info")
        def get_info():
            if not self.file_path or not os.path.exists(self.file_path):
                raise HTTPException(status_code=404, detail="No file available")
            size = os.path.getsize(self.file_path)
            count = get_chunk_count(size)
            return {
                "file_name": os.path.basename(self.file_path),
                "file_size": size,
                "total_chunks": count,
            }

        @app.get("/chunk/{index}")
        def get_chunk(index: int):
            if not self.file_path:
                raise HTTPException(status_code=404)
            size = os.path.getsize(self.file_path)
            count = get_chunk_count(size)
            if index < 0 or index >= count:
                raise HTTPException(status_code=400, detail="Invalid chunk index")
            data = read_chunk(self.file_path, index)
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
        self.file_path = None
        self.bytes_sent = 0


file_server = FileServer()
