import asyncio
import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.chunker import human_size, CHUNK_SIZE


def _add_shadow(widget, color: str = "#6c63ff", blur: int = 18, offset: int = 3):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)
from core.client import DownloadClient, FileDownloadClient, fetch_file_list
from ui.widgets import AnimatedProgressBar, StatBadge


def _fmt_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


_EXT_ICONS = {
    ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬", ".mov": "🎬", ".webm": "🎬",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".aac": "🎵",
    ".jpg": "🖼", ".jpeg": "🖼", ".png": "🖼", ".gif": "🖼", ".webp": "🖼",
    ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
    ".pdf": "📕", ".doc": "📄", ".docx": "📄", ".txt": "📄", ".xls": "📊",
    ".py": "💻", ".js": "💻", ".ts": "💻", ".exe": "⚙️", ".dmg": "💿",
}

def _file_icon(name: str) -> str:
    return _EXT_ICONS.get(os.path.splitext(name)[1].lower(), "📄")


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, float, float)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: DownloadClient, tunnel_url: str, save_dir: str):
        super().__init__()
        self.client    = client
        self.tunnel_url = tunnel_url
        self.save_dir  = save_dir

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.client.download(
                    tunnel_url=self.tunnel_url,
                    save_dir=self.save_dir,
                    progress_cb=lambda d, t, sp, eta: self.progress.emit(d, t, sp, eta),
                    done_cb=lambda ok, msg: self.finished.emit(ok, msg),
                )
            )
        finally:
            loop.close()


class FetchFileListWorker(QThread):
    ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, tunnel_url: str):
        super().__init__()
        self.tunnel_url = tunnel_url

    def run(self):
        import httpx
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(fetch_file_list(self.tunnel_url))
            self.ready.emit(result)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            self.error.emit("Could not connect — link may have expired or sender is offline")
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                self.error.emit("Could not connect — link may have expired or sender is offline")
            else:
                self.error.emit(f"Server error {e.response.status_code}")
        except Exception as e:
            msg = str(e)
            if "nodename nor servname" in msg or "name or service not known" in msg.lower() or "getaddrinfo" in msg.lower():
                self.error.emit("Could not connect — link may have expired or sender is offline")
            else:
                self.error.emit(msg)
        finally:
            loop.close()


class FileWorker(QThread):
    progress = pyqtSignal(int, int, float, float)
    finished = pyqtSignal(bool, str)

    def __init__(self, client: FileDownloadClient, tunnel_url: str, file_index: int, save_dir: str):
        super().__init__()
        self.client = client
        self.tunnel_url = tunnel_url
        self.file_index = file_index
        self.save_dir = save_dir

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.client.download(
                    tunnel_url=self.tunnel_url,
                    file_index=self.file_index,
                    save_dir=self.save_dir,
                    progress_cb=lambda d, t, sp, eta: self.progress.emit(d, t, sp, eta),
                    done_cb=lambda ok, msg: self.finished.emit(ok, msg),
                )
            )
        finally:
            loop.close()


_ICON_BTN_STYLE = (
    "QPushButton {{ background-color: {bg}; color: {fg}; border: 1.5px solid {border};"
    " border-radius: 7px; font-size: 13px; font-weight: 600; padding: 0px; }}"
    "QPushButton:hover {{ background-color: {hover}; border-color: {fg}; }}"
    "QPushButton:disabled {{ color: #3a3a60; background-color: #14141e; border-color: #2a2a40; }}"
)


class FileRow(QFrame):
    def __init__(self, file_info: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #12121e; border-radius: 12px; border: 1px solid #ffffff0d; }"
        )
        self._client = FileDownloadClient()
        self._paused = False
        self._file_info = file_info
        self._build(file_info)

    def _build(self, info: dict):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        self.setFixedHeight(70)

        # Row 1: icon + name + size + pct
        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)

        icon_lbl = QLabel(_file_icon(info["file_name"]))
        icon_lbl.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        icon_lbl.setFixedWidth(22)

        fname_lbl = QLabel(info["file_name"])
        fname_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #e0e0f8; background: transparent; border: none;")
        fname_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        size_lbl = QLabel(human_size(info["file_size"]))
        size_lbl.setStyleSheet("font-size: 11px; color: #5050a0; background: transparent; border: none;")

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet("font-size: 11px; color: #8080c0; background: transparent; border: none;")
        self._pct_lbl.setFixedWidth(34)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top.addWidget(icon_lbl)
        top.addWidget(fname_lbl, stretch=1)
        top.addWidget(size_lbl)
        top.addWidget(self._pct_lbl)

        # Row 2: progress bar + pause btn + cancel btn
        bar_row = QHBoxLayout()
        bar_row.setSpacing(6)
        bar_row.setContentsMargins(0, 0, 0, 0)

        self._progress_bar = AnimatedProgressBar()

        self._pause_btn = QPushButton("⏸")
        self._pause_btn.setFixedSize(28, 28)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setStyleSheet(_ICON_BTN_STYLE.format(
            bg="#1a1a2e", fg="#8080c0", border="#ffffff18", hover="#22223a"
        ))
        self._pause_btn.clicked.connect(self._toggle_pause)

        self._cancel_btn = QPushButton("✕")
        self._cancel_btn.setFixedSize(28, 28)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(_ICON_BTN_STYLE.format(
            bg="#1e1224", fg="#e060a0", border="#e060a040", hover="#2a1530"
        ))
        self._cancel_btn.clicked.connect(self._do_cancel)

        bar_row.addWidget(self._progress_bar, stretch=1)
        bar_row.addWidget(self._pause_btn)
        bar_row.addWidget(self._cancel_btn)

        lay.addLayout(top)
        lay.addLayout(bar_row)

    def start(self, tunnel_url: str, file_index: int, save_dir: str):
        self._worker = FileWorker(self._client, tunnel_url, file_index, save_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int, speed_mb: float, eta_s: float):
        if total > 0:
            pct = int(done * 100 / total)
            self._progress_bar.setValue(pct)
            self._pct_lbl.setText(f"{pct}%")

    def _on_finished(self, success: bool, msg: str):
        self._pause_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        if success:
            self._progress_bar.setValue(100)
            self._pct_lbl.setText("✓")
            self.setStyleSheet(
                "QFrame#card { background-color: #0e1e1a; border-radius: 16px; border: 1px solid #22c6a550; }"
            )
        else:
            self._pct_lbl.setText("✗")
        self.finished_signal_emit(success, msg)

    def finished_signal_emit(self, success, msg):
        pass

    def _toggle_pause(self):
        if self._paused:
            self._client.resume()
            self._paused = False
            self._pause_btn.setText("⏸")
        else:
            self._client.pause()
            self._paused = True
            self._pause_btn.setText("▶")

    def _do_cancel(self):
        self._client.cancel()


class ReceiverPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = DownloadClient()
        self._worker: DownloadWorker | None = None
        self._paused  = False
        self._total_size = 0
        self._file_workers: list[FileWorker] = []
        self._fetch_worker: FetchFileListWorker | None = None
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # ── Input card ────────────────────────────────────────
        input_card = QFrame()
        input_card.setObjectName("card")
        ic = QVBoxLayout(input_card)
        ic.setContentsMargins(20, 18, 20, 18)
        ic.setSpacing(14)

        lbl1 = QLabel("SHARE LINK")
        lbl1.setObjectName("sectionLabel")
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("Paste the link you received…")
        self._url_edit.textChanged.connect(self._check_ready)

        lbl2 = QLabel("SAVE TO")
        lbl2.setObjectName("sectionLabel")
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self._settings = QSettings("ShareData", "ShareData")
        saved_folder = self._settings.value("receiver/last_folder", os.path.expanduser("~/Downloads"))
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setText(saved_folder)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit, stretch=1)
        folder_row.addWidget(browse_btn)

        ic.addWidget(lbl1)
        ic.addWidget(self._url_edit)
        ic.addWidget(lbl2)
        ic.addLayout(folder_row)
        root.addWidget(input_card)

        # ── Start button ──────────────────────────────────────
        self._start_btn = QPushButton("⬇  Download Files")
        self._start_btn.setObjectName("actionBtn")
        self._start_btn.setEnabled(False)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #6c63ff; color: #ffffff; border: 1.5px solid #8b5cf6;"
            " border-radius: 12px; padding: 12px 28px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background-color: #7c73ff; }"
            "QPushButton:pressed { background-color: #5a52e0; }"
            "QPushButton:disabled { background-color: #1e1e30; color: #3a3a60; border-color: #2a2a45; }"
        )
        self._start_btn.clicked.connect(self._start_download)
        root.addWidget(self._start_btn)

        # ── Legacy progress card (hidden, kept for compat) ────
        self._progress_card = self._build_progress_card()
        self._progress_card.hide()
        root.addWidget(self._progress_card)

        # ── Files scroll area ─────────────────────────────────
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #0d0d1c; width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: #2a2a50; border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        scroll_inner = QWidget()
        scroll_inner.setStyleSheet("background: transparent;")
        self._files_area = QVBoxLayout(scroll_inner)
        self._files_area.setContentsMargins(0, 0, 4, 0)
        self._files_area.setSpacing(6)
        self._files_area.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll_area.setWidget(scroll_inner)
        self._scroll_area.hide()
        root.addWidget(self._scroll_area, stretch=1)

        # ── Status label ──────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

    def _build_progress_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 20)
        lay.setSpacing(14)

        name_row = QHBoxLayout()
        self._dl_icon = QLabel("📄")
        self._dl_icon.setStyleSheet("font-size: 22px; background: transparent;")
        self._dl_fname = QLabel("Connecting…")
        self._dl_fname.setObjectName("fileNameLabel")
        self._dl_fname.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name_row.addWidget(self._dl_icon)
        name_row.addWidget(self._dl_fname, stretch=1)

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setObjectName("pctLabel")
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_bar = AnimatedProgressBar()

        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        self._speed_badge    = StatBadge("↓", "—", color="#6c63ff")
        self._size_badge     = StatBadge("📁", "—", color="#22c6a5")
        self._eta_badge      = StatBadge("⏱", "—", color="#f59e0b")
        self._speed_badge.setFixedWidth(110)
        self._size_badge.setFixedWidth(150)
        self._eta_badge.setFixedWidth(90)
        badges_row.addStretch()
        badges_row.addWidget(self._speed_badge)
        badges_row.addWidget(self._size_badge)
        badges_row.addWidget(self._eta_badge)
        badges_row.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._pause_btn = QPushButton("⏸   Pause")
        self._pause_btn.setObjectName("secondaryBtn")
        self._pause_btn.setMinimumWidth(120)
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._cancel_btn = QPushButton("✕   Cancel")
        self._cancel_btn.setObjectName("dangerBtn")
        self._cancel_btn.setMinimumWidth(120)
        self._cancel_btn.clicked.connect(self._cancel_download)
        btn_row.addStretch()
        btn_row.addWidget(self._pause_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()

        lay.addLayout(name_row)
        lay.addWidget(self._pct_lbl)
        lay.addWidget(self._progress_bar)
        lay.addLayout(badges_row)
        lay.addLayout(btn_row)
        return card

    # ── Slots ──────────────────────────────────────────────────────────────

    def _check_ready(self):
        url    = self._url_edit.text().strip()
        folder = self._folder_edit.text().strip()
        self._file_workers = [w for w in self._file_workers if w.isRunning()]
        running = self._worker is not None or bool(self._file_workers) or self._fetch_worker is not None
        ready  = url.startswith("http") and bool(folder)
        self._start_btn.setEnabled(ready and not running)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose save folder", self._folder_edit.text()
        )
        if folder:
            self._folder_edit.setText(folder)
            self._settings.setValue("receiver/last_folder", folder)
            self._check_ready()

    def _start_download(self):
        url    = self._url_edit.text().strip()
        folder = self._folder_edit.text().strip()
        if not url or not folder:
            return

        self._start_btn.setEnabled(False)

        # Cancel any still-running workers from a previous session
        for w in self._file_workers:
            if w.isRunning():
                w.client.cancel()

        # Clear UI from any previous session
        while self._files_area.count() > 0:
            item = self._files_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._scroll_area.hide()
        self._file_workers = []
        self._status_lbl.setText("Fetching file list…")
        self._status_lbl.setStyleSheet("color: #8080b0; font-size: 12px;")

        self._fetch_worker = FetchFileListWorker(url)
        self._fetch_worker.ready.connect(lambda files: self._on_file_list(files, url, folder))
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.start()

    def _on_file_list(self, files: list, tunnel_url: str, save_dir: str):
        self._fetch_worker = None
        self._status_lbl.setText("")
        self._status_lbl.setStyleSheet("")

        if not files:
            self._status_lbl.setStyleSheet("color: #f59e0b; font-size: 12px;")
            self._status_lbl.setText("⚠  No files available on this link.")
            self._check_ready()
            return

        self._scroll_area.show()

        for info in files:
            row = FileRow(info)
            row.finished_signal_emit = lambda ok, msg, r=row: self._on_file_row_finished(r, ok, msg)
            self._files_area.insertWidget(self._files_area.count() - 1, row)
            worker = FileWorker(row._client, tunnel_url, info["index"], save_dir)
            worker.progress.connect(row._on_progress)
            worker.finished.connect(lambda ok, msg, r=row: self._on_file_row_finished(r, ok, msg))
            row._worker = worker
            self._file_workers.append(worker)
            worker.start()

    def _on_file_row_finished(self, row: "FileRow", success: bool, msg: str):
        row._pause_btn.setEnabled(False)
        row._cancel_btn.setEnabled(False)
        if success:
            row._progress_bar.setValue(100)
            row._pct_lbl.setText("✓")
            row.setStyleSheet(
                "QFrame { background-color: #0e1e1a; border-radius: 12px; border: 1px solid #22c6a550; }"
            )
        elif msg == "cancelled":
            row._pct_lbl.setStyleSheet("font-size: 11px; color: #f59e0b; background: transparent; border: none;")
            row._pct_lbl.setText("—")
            row.setStyleSheet(
                "QFrame { background-color: #1a150a; border-radius: 12px; border: 1px solid #f59e0b40; }"
            )
        elif msg == "sender_gone":
            row._pct_lbl.setStyleSheet("font-size: 11px; color: #f06080; background: transparent; border: none;")
            row._pct_lbl.setText("!")
            row.setStyleSheet(
                "QFrame { background-color: #1a0e12; border-radius: 12px; border: 1px solid #f0608050; }"
            )
            self._status_lbl.setStyleSheet("color: #f06080; font-size: 12px;")
            self._status_lbl.setText("Sender stopped sharing")
        else:
            row._pct_lbl.setText("✗")
            self._status_lbl.setStyleSheet("color: #f06080; font-size: 12px;")
            self._status_lbl.setText(f"⚠  {msg}")

        self._file_workers = [w for w in self._file_workers if w.isRunning()]
        self._check_ready()

    def _on_fetch_error(self, err: str):
        self._fetch_worker = None
        self._status_lbl.setStyleSheet("color: #f06080; font-size: 12px;")
        self._status_lbl.setText(f"⚠  {err}")
        self._check_ready()

    def _on_progress(self, done: int, total: int, speed_mb: float, eta_s: float):
        if self._client.current_file_name:
            self._dl_fname.setText(self._client.current_file_name)
        if total > 0:
            pct = int(done * 100 / total)
            self._progress_bar.setValue(pct)
            self._pct_lbl.setText(f"{pct}%")
            done_b  = min(done * CHUNK_SIZE, self._client.current_file_size or total * CHUNK_SIZE)
            total_b = self._client.current_file_size or total * CHUNK_SIZE
            self._size_badge.setValue(f"{human_size(done_b)} / {human_size(total_b)}")
            self._total_size = total_b

        self._speed_badge.setValue(f"{speed_mb:.1f} MB/s")
        self._eta_badge.setValue(_fmt_eta(eta_s))

    def _on_finished(self, success: bool, msg: str):
        self._worker = None
        self._pause_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._check_ready()

        if success:
            self._progress_bar.setValue(100)
            self._pct_lbl.setText("100%")
            fname = os.path.basename(msg)
            self._dl_fname.setText(fname)
            self._progress_card.setObjectName("successCard")
            self._progress_card.setStyleSheet(
                "QFrame#successCard { background-color: #0e1e1a; border-radius: 16px; border: 1px solid #22c6a550; }"
            )
            self._status_lbl.setStyleSheet("color: #22c6a5; font-size: 12px;")
            self._status_lbl.setText(f"✓  Saved to  {msg}")

        elif msg == "cancelled":
            self._progress_card.hide()
            self._status_lbl.setStyleSheet("color: #f59e0b; font-size: 12px;")
            self._status_lbl.setText("⏹  Cancelled — progress saved. Paste the link again to resume.")

        else:
            self._status_lbl.setStyleSheet("color: #f06080; font-size: 12px;")
            self._status_lbl.setText(f"⚠  {msg}")

    def _toggle_pause(self):
        if self._paused:
            self._client.resume()
            self._paused = False
            self._pause_btn.setText("⏸   Pause")
            self._status_lbl.setStyleSheet("")
            self._status_lbl.setText("")
        else:
            self._client.pause()
            self._paused = True
            self._pause_btn.setText("▶   Resume")
            self._status_lbl.setStyleSheet("color: #f59e0b; font-size: 12px;")
            self._status_lbl.setText("⏸  Paused — click Resume to continue")

    def _cancel_download(self):
        self._client.cancel()
