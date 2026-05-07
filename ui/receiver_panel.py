import asyncio
import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.chunker import human_size, CHUNK_SIZE
from core.client import DownloadClient
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


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, float, float)  # done, total, speed_mb, eta_s
    finished = pyqtSignal(bool, str)               # success, path_or_msg

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


class ReceiverPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = DownloadClient()
        self._worker: DownloadWorker | None = None
        self._paused  = False
        self._total_size = 0
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

        # Link field
        lbl1 = QLabel("SHARE LINK")
        lbl1.setObjectName("sectionLabel")
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("Paste the link you received…")
        self._url_edit.textChanged.connect(self._check_ready)

        # Folder field
        lbl2 = QLabel("SAVE TO")
        lbl2.setObjectName("sectionLabel")
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setText(os.path.expanduser("~/Downloads"))
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit, stretch=1)
        folder_row.addWidget(browse_btn)

        ic.addWidget(lbl1)
        ic.addWidget(self._url_edit)
        ic.addWidget(lbl2)
        ic.addLayout(folder_row)
        root.addWidget(input_card)

        # ── Start button ──────────────────────────────────────
        self._start_btn = QPushButton("⬇   Start Download")
        self._start_btn.setObjectName("actionBtn")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start_download)
        root.addWidget(self._start_btn)

        # ── Progress card (hidden initially) ──────────────────
        self._progress_card = self._build_progress_card()
        self._progress_card.hide()
        root.addWidget(self._progress_card)

        # ── Status label ──────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        root.addStretch()

    def _build_progress_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 20)
        lay.setSpacing(14)

        # File name row
        name_row = QHBoxLayout()
        self._dl_icon = QLabel("📄")
        self._dl_icon.setStyleSheet("font-size: 22px; background: transparent;")
        self._dl_fname = QLabel("Connecting…")
        self._dl_fname.setObjectName("fileNameLabel")
        name_row.addWidget(self._dl_icon)
        name_row.addWidget(self._dl_fname, stretch=1)

        # Percentage
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setObjectName("pctLabel")
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Custom animated progress bar
        self._progress_bar = AnimatedProgressBar()

        # Stat badges row
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        self._speed_badge    = StatBadge("↓", "—", color="#6c63ff")
        self._size_badge     = StatBadge("📁", "—", color="#22c6a5")
        self._eta_badge      = StatBadge("⏱", "—", color="#f59e0b")
        badges_row.addStretch()
        badges_row.addWidget(self._speed_badge)
        badges_row.addWidget(self._size_badge)
        badges_row.addWidget(self._eta_badge)
        badges_row.addStretch()

        # Control buttons
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
        ready  = url.startswith("http") and bool(folder)
        self._start_btn.setEnabled(ready and self._worker is None)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose save folder", self._folder_edit.text()
        )
        if folder:
            self._folder_edit.setText(folder)
            self._check_ready()

    def _start_download(self):
        url    = self._url_edit.text().strip()
        folder = self._folder_edit.text().strip()
        if not url or not folder:
            return

        self._paused  = False
        self._total_size = 0
        self._start_btn.setEnabled(False)
        self._progress_card.show()
        self._dl_fname.setText("Connecting…")
        self._dl_icon.setText("📄")
        self._progress_bar.setValue(0)
        self._pct_lbl.setText("0%")
        self._status_lbl.setText("")
        self._status_lbl.setStyleSheet("")
        self._pause_btn.setText("⏸   Pause")
        self._pause_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)

        self._worker = DownloadWorker(self._client, url, folder)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int, speed_mb: float, eta_s: float):
        # Show filename and size as soon as we hear from the server
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
