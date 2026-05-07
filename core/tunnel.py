import os
import platform
import re
import shutil
import stat
import subprocess
import threading
import urllib.request
from typing import Callable, Optional


CLOUDFLARED_RELEASES = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
)

_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")


def _app_bin_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".sharedata", "bin")
    os.makedirs(d, exist_ok=True)
    return d


def _binary_name() -> str:
    return "cloudflared.exe" if platform.system() == "Windows" else "cloudflared"


def get_cloudflared(
    status_cb: Optional[Callable[[str], None]] = None
) -> str:
    """Return path to cloudflared, downloading it if needed."""
    # 1. Check PATH
    found = shutil.which("cloudflared")
    if found:
        return found

    # 2. Check our cache dir
    cache_path = os.path.join(_app_bin_dir(), _binary_name())
    if os.path.exists(cache_path):
        return cache_path

    # 3. Download
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        fname = "cloudflared-darwin-arm64" if "arm" in machine else "cloudflared-darwin-amd64"
    elif system == "windows":
        fname = "cloudflared-windows-amd64.exe"
    else:
        fname = "cloudflared-linux-amd64"

    url = CLOUDFLARED_RELEASES + fname
    if status_cb:
        status_cb("Downloading cloudflared (first-time setup, ~30 MB)...")

    urllib.request.urlretrieve(url, cache_path)

    if system != "windows":
        current = os.stat(cache_path).st_mode
        os.chmod(cache_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return cache_path


class TunnelManager:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self.tunnel_url: Optional[str] = None

    def start(
        self,
        port: int,
        url_cb: Callable[[str], None],
        error_cb: Callable[[str], None],
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        def run():
            try:
                binary = get_cloudflared(status_cb)
                self._process = subprocess.Popen(
                    [binary, "tunnel", "--url", f"http://localhost:{port}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if status_cb:
                    status_cb("Starting tunnel...")
                for line in self._process.stdout:
                    match = _URL_PATTERN.search(line)
                    if match:
                        self.tunnel_url = match.group(0)
                        url_cb(self.tunnel_url)
                        break
                # Keep process alive — just drain remaining output
                for _ in self._process.stdout:
                    pass
                self._process.wait()
            except Exception as e:
                error_cb(str(e))

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None
        self.tunnel_url = None


tunnel_manager = TunnelManager()
