import os
import platform
import re
import shutil
import stat
import subprocess
import threading
from typing import Callable, Optional


_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")


def _app_bin_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".sharedata", "bin")
    os.makedirs(d, exist_ok=True)
    return d


def _binary_name() -> str:
    return "cloudflared.exe" if platform.system() == "Windows" else "cloudflared"


def _download_cloudflared(dest: str, status_cb) -> None:
    import httpx, tarfile

    system  = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        arch   = "arm64" if "arm" in machine else "amd64"
        fname  = f"cloudflared-darwin-{arch}.tgz"
        is_tgz = True
    elif system == "windows":
        fname  = "cloudflared-windows-amd64.exe"
        is_tgz = False
    else:
        fname  = "cloudflared-linux-amd64"
        is_tgz = False

    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{fname}"

    if status_cb:
        status_cb("Downloading cloudflared (~30 MB, one-time setup)...")

    tmp = dest + (".tgz" if is_tgz else ".tmp")
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if status_cb and total:
                        pct = int(downloaded * 100 / total)
                        status_cb(f"Downloading cloudflared... {pct}%")

    if is_tgz:
        if status_cb:
            status_cb("Extracting cloudflared...")
        with tarfile.open(tmp, "r:gz") as tar:
            member = next(
                (m for m in tar.getmembers() if m.name.endswith("cloudflared") and m.isfile()),
                None,
            )
            if member is None:
                raise RuntimeError("cloudflared binary not found inside archive")
            member.name = os.path.basename(dest)
            tar.extract(member, path=os.path.dirname(dest))
        os.remove(tmp)
    else:
        os.replace(tmp, dest)

    if system != "windows":
        current = os.stat(dest).st_mode
        os.chmod(dest, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def get_cloudflared(status_cb=None) -> str:
    found = shutil.which("cloudflared")
    if found:
        return found

    cache_path = os.path.join(_app_bin_dir(), _binary_name())
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1_000_000:
        return cache_path

    _download_cloudflared(cache_path, status_cb)
    return cache_path


class TunnelManager:
    def __init__(self):
        self._process = None
        self._thread  = None
        self.tunnel_url = None

    def start(self, port, url_cb, error_cb, status_cb=None):
        def run():
            try:
                binary = get_cloudflared(status_cb)
                if status_cb:
                    status_cb("Starting tunnel...")

                kwargs = dict(
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if platform.system() == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    kwargs["startupinfo"] = si
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

                self._process = subprocess.Popen(
                    [binary, "tunnel", "--url", f"http://localhost:{port}"],
                    **kwargs,
                )

                proc = self._process
                url_found = False
                for line in proc.stdout:
                    match = _URL_PATTERN.search(line)
                    if match:
                        self.tunnel_url = match.group(0)
                        url_cb(self.tunnel_url)
                        url_found = True
                        break
                    if "error" in line.lower() and status_cb:
                        status_cb(f"cloudflared: {line.strip()}")

                if not url_found:
                    error_cb("Tunnel closed before a URL was assigned. Check your internet connection.")
                    return

                for _ in proc.stdout:
                    pass
                proc.wait()

            except FileNotFoundError:
                error_cb("cloudflared binary not found and could not be downloaded.")
            except Exception as e:
                error_cb(str(e))

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None
        self.tunnel_url = None


tunnel_manager = TunnelManager()
