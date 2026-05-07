import io
import os
import time

import qrcode
from PIL import Image
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QPainter, QColor, QLinearGradient
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QGraphicsDropShadowEffect,
)

from core.chunker import human_size
from core.server import file_server
from core.tunnel import tunnel_manager
from ui.widgets import SpinnerWidget, StatBadge


# ── File-type icons ────────────────────────────────────────────────────────

_EXT_ICONS = {
    ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬", ".mov": "🎬", ".webm": "🎬",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".aac": "🎵",
    ".jpg": "🖼", ".jpeg": "🖼", ".png": "🖼", ".gif": "🖼", ".webp": "🖼",
    ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
    ".pdf": "📕", ".doc": "📄", ".docx": "📄", ".txt": "📄", ".xls": "📊",
    ".py": "💻", ".js": "💻", ".ts": "💻", ".exe": "⚙️", ".dmg": "💿",
}

def _file_icon(path: str) -> str:
    return _EXT_ICONS.get(os.path.splitext(path)[1].lower(), "📄")


# ── QR helper ─────────────────────────────────────────────────────────────

def _make_qr_pixmap(url: str, size: int = 160) -> QPixmap:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#f0f0ff", back_color="#0d0d1c")
    img = img.resize((size, size), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    px = QPixmap()
    px.loadFromData(buf.read())
    return px


# ── Drop Zone ──────────────────────────────────────────────────────────────

class DropZone(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self._icon_lbl = QLabel("📂")
        self._icon_lbl.setObjectName("dropIcon")
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._hint = QLabel("Drop your file here")
        self._hint.setObjectName("dropHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._sub = QLabel("or click to browse")
        self._sub.setObjectName("dropHintSub")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._hint)
        layout.addWidget(self._sub)

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(self, "Select file to share")
        if path:
            self.file_dropped.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setObjectName("dropZoneHover")
            self.setStyleSheet("QFrame#dropZoneHover { background-color: #12103a; border-radius: 16px; border: 2px dashed #6c63ff; }")
            self._icon_lbl.setText("📥")

    def dragLeaveEvent(self, event):
        self.setObjectName("dropZone")
        self.setStyleSheet("")
        self._icon_lbl.setText("📂")

    def dropEvent(self, event: QDropEvent):
        self.setObjectName("dropZone")
        self.setStyleSheet("")
        self._icon_lbl.setText("📂")
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isfile(path):
                self.file_dropped.emit(path)


# ── Tunnel Worker ──────────────────────────────────────────────────────────

class TunnelWorker(QThread):
    url_ready = pyqtSignal(str)
    error     = pyqtSignal(str)
    status    = pyqtSignal(str)

    def __init__(self, port: int):
        super().__init__()
        self.port = port

    def run(self):
        tunnel_manager.start(
            port=self.port,
            url_cb=lambda u: self.url_ready.emit(u),
            error_cb=lambda e: self.error.emit(e),
            status_cb=lambda s: self.status.emit(s),
        )


# ── Loading Card ───────────────────────────────────────────────────────────

class LoadingCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(110)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner_row = QHBoxLayout()
        spinner_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner = SpinnerWidget(size=32, color="#6c63ff")
        spinner_row.addWidget(self._spinner)

        self._status = QLabel("Starting…")
        self._status.setObjectName("statusLabel")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addLayout(spinner_row)
        lay.addWidget(self._status)

    def start(self, msg: str = "Starting tunnel…"):
        self._status.setText(msg)
        self._spinner.start()

    def set_status(self, msg: str):
        self._status.setText(msg)

    def stop(self):
        self._spinner.stop()


# ── Sender Panel ───────────────────────────────────────────────────────────

class SenderPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = ""
        self._sharing = False
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(900)
        self._stats_timer.timeout.connect(self._update_stats)
        self._session_start = 0.0
        self._tunnel_worker: TunnelWorker | None = None
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # Drop zone
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_chosen)
        root.addWidget(self._drop_zone)

        # File card (hidden initially)
        self._file_card = self._build_file_card()
        self._file_card.hide()
        root.addWidget(self._file_card)

        # Loading card (hidden initially)
        self._loading_card = LoadingCard()
        self._loading_card.hide()
        root.addWidget(self._loading_card)

        # Share card (hidden initially)
        self._share_card = self._build_share_card()
        self._share_card.hide()
        root.addWidget(self._share_card)

        # Primary action button
        self._action_btn = QPushButton("🚀   Start Sharing")
        self._action_btn.setObjectName("actionBtn")
        self._action_btn.setEnabled(False)
        self._action_btn.clicked.connect(self._toggle_sharing)
        root.addWidget(self._action_btn)

        # Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        root.addStretch()

    def _build_file_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        self._ftype_icon = QLabel("📄")
        self._ftype_icon.setStyleSheet("font-size: 30px; background: transparent;")
        self._ftype_icon.setFixedWidth(36)

        info = QVBoxLayout()
        info.setSpacing(3)
        self._fname_lbl = QLabel()
        self._fname_lbl.setObjectName("fileNameLabel")
        self._fsize_lbl = QLabel()
        self._fsize_lbl.setObjectName("fileSizeLabel")
        info.addWidget(self._fname_lbl)
        info.addWidget(self._fsize_lbl)

        change_btn = QPushButton("Change")
        change_btn.setObjectName("secondaryBtn")
        change_btn.setFixedWidth(78)
        change_btn.clicked.connect(self._change_file)

        lay.addWidget(self._ftype_icon)
        lay.addLayout(info, stretch=1)
        lay.addWidget(change_btn)
        return card

    def _build_share_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("liveCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # Live badge row
        badge_row = QHBoxLayout()
        live_dot = QLabel("⬤  LIVE")
        live_dot.setObjectName("liveDot")
        badge_row.addWidget(live_dot)
        badge_row.addStretch()

        # URL row
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self._url_edit = QLineEdit()
        self._url_edit.setReadOnly(True)
        self._url_edit.setPlaceholderText("Generating link…")
        self._copy_btn = QPushButton("Copy Link")
        self._copy_btn.setObjectName("copyBtn")
        self._copy_btn.setFixedWidth(94)
        self._copy_btn.clicked.connect(self._copy_url)
        url_row.addWidget(self._url_edit, stretch=1)
        url_row.addWidget(self._copy_btn)

        hint = QLabel("Share this link with the receiver")
        hint.setObjectName("qrHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # QR code in a centered frame
        qr_frame = QFrame()
        qr_frame.setObjectName("card")
        qr_frame.setFixedSize(184, 184)
        qr_lay = QVBoxLayout(qr_frame)
        qr_lay.setContentsMargins(8, 8, 8, 8)
        self._qr_lbl = QLabel()
        self._qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_lay.addWidget(self._qr_lbl)

        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(qr_frame)
        qr_row.addStretch()

        # Stats badges
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._speed_badge = StatBadge("↑", "—  MB/s", color="#6c63ff")
        self._sent_badge  = StatBadge("📤", "—", color="#22c6a5")
        stats_row.addStretch()
        stats_row.addWidget(self._speed_badge)
        stats_row.addWidget(self._sent_badge)
        stats_row.addStretch()

        # Stop button
        self._stop_btn = QPushButton("⏹   Stop Sharing")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.clicked.connect(self._stop_sharing)

        lay.addLayout(badge_row)
        lay.addLayout(url_row)
        lay.addWidget(hint)
        lay.addLayout(qr_row)
        lay.addLayout(stats_row)
        lay.addWidget(self._stop_btn)
        return card

    # ── Slots ──────────────────────────────────────────────────────────────

    def _on_file_chosen(self, path: str):
        self._file_path = path
        self._ftype_icon.setText(_file_icon(path))
        self._fname_lbl.setText(os.path.basename(path))
        self._fsize_lbl.setText(human_size(os.path.getsize(path)))
        self._drop_zone.hide()
        self._file_card.show()
        self._action_btn.setEnabled(True)

    def _change_file(self):
        self._stop_sharing()
        self._drop_zone.show()
        self._file_card.hide()
        self._share_card.hide()
        self._action_btn.setEnabled(False)
        self._action_btn.setText("🚀   Start Sharing")
        self._action_btn.setObjectName("actionBtn")
        self._action_btn.setStyleSheet("")
        self._file_path = ""

    def _toggle_sharing(self):
        if self._sharing:
            self._stop_sharing()
        else:
            self._start_sharing()

    def _start_sharing(self):
        self._sharing = True
        self._action_btn.setEnabled(False)
        self._status_lbl.setText("")

        file_server.set_file(self._file_path)
        file_server.start()

        self._loading_card.start("Starting tunnel (first time may take 20 s)…")
        self._loading_card.show()
        self._share_card.hide()

        self._tunnel_worker = TunnelWorker(port=file_server.port)
        self._tunnel_worker.url_ready.connect(self._on_tunnel_url)
        self._tunnel_worker.error.connect(self._on_tunnel_error)
        self._tunnel_worker.status.connect(self._loading_card.set_status)
        self._tunnel_worker.start()

    def _stop_sharing(self):
        if not self._sharing:
            return
        self._sharing = False
        self._stats_timer.stop()
        tunnel_manager.stop()
        file_server.stop()
        self._loading_card.stop()
        self._loading_card.hide()
        self._share_card.hide()
        self._action_btn.setEnabled(bool(self._file_path))
        self._action_btn.setText("🚀   Start Sharing")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setText("")

    def _on_tunnel_url(self, url: str):
        self._loading_card.stop()
        self._loading_card.hide()

        self._url_edit.setText(url)
        px = _make_qr_pixmap(url, size=164)
        self._qr_lbl.setPixmap(px)

        self._share_card.show()
        self._action_btn.setEnabled(True)

        self._status_lbl.setObjectName("statusOk")
        self._status_lbl.setStyleSheet("color: #22c6a5; font-size: 12px;")
        self._status_lbl.setText("✓  Sharing active — send the link to your friend")

        file_server.bytes_sent = 0
        self._session_start = time.monotonic()
        self._stats_timer.start()

    def _on_tunnel_error(self, err: str):
        self._sharing = False
        self._loading_card.stop()
        self._loading_card.hide()
        self._action_btn.setEnabled(bool(self._file_path))
        self._action_btn.setText("🚀   Start Sharing")
        self._status_lbl.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self._status_lbl.setText(f"⚠  Tunnel error: {err}")

    def _copy_url(self):
        url = self._url_edit.text()
        if url:
            QApplication.clipboard().setText(url)
            self._copy_btn.setText("✓ Copied!")
            QTimer.singleShot(2200, lambda: self._copy_btn.setText("Copy Link"))

    def _update_stats(self):
        elapsed = time.monotonic() - self._session_start
        total   = file_server.bytes_sent
        speed   = total / elapsed / 1_048_576 if elapsed > 0 else 0
        self._speed_badge.setValue(f"{speed:.1f} MB/s")
        self._sent_badge.setValue(human_size(total))
