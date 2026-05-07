import asyncio
import os
import time
from typing import Callable, Optional

import httpx

from core.chunker import chunk_hash, get_chunk_offset, CHUNK_SIZE
from core.manifest import Manifest, manifest_path, save_manifest, load_manifest


class DownloadClient:
    def __init__(self):
        self._pause_event = asyncio.Event()
        self._cancel_flag = False
        self.current_file_name: str = ""
        self.current_file_size: int = 0

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def cancel(self):
        self._cancel_flag = True
        self._pause_event.set()

    def reset(self):
        self._cancel_flag = False
        self._pause_event.set()

    async def download(
        self,
        tunnel_url: str,
        save_dir: str,
        progress_cb: Callable[[int, int, float, float], None],
        done_cb: Callable[[bool, str], None],
    ):
        """
        progress_cb(chunks_done, total_chunks, speed_mb_per_sec, eta_seconds)
        done_cb(success, message_or_save_path)
        """
        self.reset()
        tunnel_url = tunnel_url.rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Retry /info up to 5 times — tunnel may take a moment to route
                info = None
                last_error = ""
                for attempt in range(5):
                    try:
                        resp = await client.get(f"{tunnel_url}/info")
                        if resp.status_code == 404:
                            last_error = "Sender is not sharing a file yet. Make sure they clicked 'Start Sharing' first."
                            await asyncio.sleep(2)
                            continue
                        resp.raise_for_status()
                        info = resp.json()
                        break
                    except Exception as e:
                        last_error = str(e)
                        if attempt < 4:
                            await asyncio.sleep(3)

                if info is None:
                    done_cb(False, last_error or "Could not reach sender. Check the link and try again.")
                    return

                file_name: str = info["file_name"]
                file_size: int = info["file_size"]
                total_chunks: int = info["total_chunks"]
                self.current_file_name = file_name
                self.current_file_size = file_size

                save_path = os.path.join(save_dir, file_name)
                mpath = manifest_path(save_path)

                # Try to resume an existing partial download for the same file
                manifest = load_manifest(mpath)
                if (
                    manifest is not None
                    and manifest.file_name == file_name
                    and manifest.file_size == file_size
                    and manifest.total_chunks == total_chunks
                ):
                    manifest.tunnel_url = tunnel_url  # URL may have changed
                else:
                    manifest = Manifest(
                        file_name=file_name,
                        file_size=file_size,
                        total_chunks=total_chunks,
                        save_path=save_path,
                        tunnel_url=tunnel_url,
                    )

                # Pre-allocate file (sparse where OS supports it)
                if not os.path.exists(save_path) or os.path.getsize(save_path) != file_size:
                    with open(save_path, "wb") as f:
                        if file_size > 0:
                            f.seek(file_size - 1)
                            f.write(b"\x00")

                pending = manifest.pending_chunks()
                start_time = time.monotonic()
                bytes_this_session = 0

                with open(save_path, "r+b") as f:
                    for chunk_index in pending:
                        if self._cancel_flag:
                            save_manifest(manifest, mpath)
                            done_cb(False, "cancelled")
                            return

                        # Block here while paused
                        await self._pause_event.wait()

                        if self._cancel_flag:
                            save_manifest(manifest, mpath)
                            done_cb(False, "cancelled")
                            return

                        # Download with up to 3 retries
                        success = False
                        for attempt in range(3):
                            try:
                                chunk_resp = await client.get(
                                    f"{tunnel_url}/chunk/{chunk_index}",
                                    timeout=httpx.Timeout(connect=15.0, read=120.0, write=10.0, pool=5.0),
                                )
                                chunk_resp.raise_for_status()
                                data = chunk_resp.content
                                expected_hash = chunk_resp.headers.get("X-Chunk-Hash", "")

                                if expected_hash and chunk_hash(data) != expected_hash:
                                    if attempt < 2:
                                        await asyncio.sleep(1)
                                        continue
                                    raise ValueError(f"Hash mismatch on chunk {chunk_index}")

                                f.seek(get_chunk_offset(chunk_index))
                                f.write(data)

                                manifest.completed_chunks.append(chunk_index)
                                save_manifest(manifest, mpath)

                                bytes_this_session += len(data)
                                elapsed = time.monotonic() - start_time
                                speed_mb = (bytes_this_session / elapsed / 1_048_576) if elapsed > 0 else 0.0

                                remaining_chunks = total_chunks - len(manifest.completed_chunks)
                                eta = (remaining_chunks * CHUNK_SIZE / (bytes_this_session / elapsed)) if elapsed > 0 and bytes_this_session > 0 else 0.0

                                progress_cb(len(manifest.completed_chunks), total_chunks, speed_mb, eta)
                                success = True
                                break

                            except Exception as e:
                                if attempt == 2:
                                    save_manifest(manifest, mpath)
                                    done_cb(False, f"Failed on chunk {chunk_index}: {e}")
                                    return
                                await asyncio.sleep(2 ** attempt)

                # Remove manifest — download is complete
                if os.path.exists(mpath):
                    os.remove(mpath)

                done_cb(True, save_path)

        except Exception as e:
            done_cb(False, str(e))
