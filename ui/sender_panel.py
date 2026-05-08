import io
import os
import time

import qrcode
from PIL import Image
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF, QSettings
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
    QScrollArea,
)

from core.chunker import human_size


def _add_shadow(widget, color: str = "#6c63ff", blur: int = 18, offset: int = 3):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)
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
    files_dropped = pyqtSignal(list)

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

        self._hint = QLabel("Drop your files here")
        self._hint.setObjectName("dropHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._sub = QLabel("or click to browse")
        self._sub.setObjectName("dropHintSub")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._hint)
        layout.addWidget(self._sub)

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()

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
        paths = [u.toLocalFile() for u in urls if os.path.isfile(u.toLocalFile())]
        if paths:
            self.files_dropped.emit(paths)


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
        self._files: list[str] = []
        self._sharing = False
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(900)
        self._stats_timer.timeout.connect(self._update_stats)
        self._session_start = 0.0
        self._tunnel_worker: TunnelWorker | None = None
        self._settings = QSettings("ShareData", "ShareData")
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # Drop zone
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_chosen)
        self._drop_zone.clicked.connect(self._browse_files)
        root.addWidget(self._drop_zone)

        # File list card (hidden initially)
        self._file_list_card = self._build_file_list_card()
        self._file_list_card.hide()
        root.addWidget(self._file_list_card)

        # Loading card (hidden initially)
        self._loading_card = LoadingCard()
        self._loading_card.hide()
        root.addWidget(self._loading_card)

        # Share card (hidden initially)
        self._share_card = self._build_share_card()
        self._share_card.hide()
        root.addWidget(self._share_card)

        # Primary action button
        self._action_btn = QPushButton("⬆  Share File")
        self._action_btn.setObjectName("actionBtn")
        self._action_btn.setEnabled(False)
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setStyleSheet(
            "QPushButton { background-color: #6c63ff; color: #ffffff; border: 1.5px solid #8b5cf6;"
            " border-radius: 12px; padding: 12px 28px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background-color: #7c73ff; }"
            "QPushButton:pressed { background-color: #5a52e0; }"
            "QPushButton:disabled { background-color: #1e1e30; color: #3a3a60; border-color: #2a2a45; }"
        )
        self._action_btn.clicked.connect(self._toggle_sharing)
        root.addWidget(self._action_btn)

        # Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        root.addStretch()

    def _build_file_list_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        self._file_rows_layout = QVBoxLayout()
        self._file_rows_layout.setSpacing(6)
        outer.addLayout(self._file_rows_layout)

        add_btn = QPushButton("＋  Add more files")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            "QPushButton { background-color: #1a1a28; color: #8080b0; border: 1.5px solid #ffffff12;"
            " border-radius: 10px; padding: 9px 18px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { border-color: #6c63ff60; color: #c0c0e8; background-color: #1e1e32; }"
        )
        add_btn.clicked.connect(self._add_more_files)
        outer.addWidget(add_btn)
        return card

    def _add_file_row(self, path: str):
        row = QFrame()
        row.setObjectName("card")
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(10, 8, 10, 8)
        row_lay.setSpacing(10)

        icon_lbl = QLabel(_file_icon(path))
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent;")
        icon_lbl.setFixedWidth(28)

        fname_lbl = QLabel(os.path.basename(path))
        fname_lbl.setObjectName("fileNameLabel")
        fname_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        size_lbl = QLabel(human_size(os.path.getsize(path)))
        size_lbl.setObjectName("fileSizeLabel")
        size_lbl.setFixedWidth(60)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(26, 26)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(
            "QPushButton { background-color: #1e1224; color: #e060a0; border: 1.5px solid #e060a070;"
            " border-radius: 6px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #2a1530; border-color: #e060a0; color: #ff80c0; }"
        )
        remove_btn.clicked.connect(lambda: self._remove_file(path, row))

        row_lay.addWidget(icon_lbl)
        row_lay.addWidget(fname_lbl, stretch=1)
        row_lay.addWidget(size_lbl)
        row_lay.addWidget(remove_btn)
        self._file_rows_layout.addWidget(row)

    def _remove_file(self, path: str, row: QFrame):
        if path in self._files:
            self._files.remove(path)
        row.setParent(None)
        row.deleteLater()
        if not self._files:
            self._file_list_card.hide()
            self._drop_zone.show()
            self._action_btn.setEnabled(False)
            self._action_btn.setText("⬆  Share File")
        else:
            self._action_btn.setText("⬆  Share Files" if len(self._files) > 1 else "⬆  Share File")

    def _build_share_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("liveCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        live_dot = QLabel("⬤")
        live_dot.setObjectName("liveDot")
        live_dot.setFixedWidth(16)

        self._url_edit = QLineEdit()
        self._url_edit.setReadOnly(True)
        self._url_edit.setPlaceholderText("Generating link…")
        self._url_edit.setCursor(Qt.CursorShape.IBeamCursor)
        self._url_edit.setTextMargins(4, 0, 4, 0)

        self._copy_btn = QPushButton("Copy Link")
        self._copy_btn.setObjectName("copyBtn")
        self._copy_btn.setFixedWidth(100)
        self._copy_btn.setStyleSheet(
            "QPushButton { background-color: #1a1a28; color: #6c63ff; border: 1.5px solid #6c63ff40;"
            " border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #20203a; border-color: #6c63ff; }"
        )
        self._copy_btn.clicked.connect(self._copy_url)

        url_row.addWidget(live_dot)
        url_row.addWidget(self._url_edit, stretch=1)
        url_row.addWidget(self._copy_btn)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        qr_frame = QFrame()
        qr_frame.setObjectName("card")
        qr_frame.setFixedSize(148, 148)
        qr_lay = QVBoxLayout(qr_frame)
        qr_lay.setContentsMargins(6, 6, 6, 6)
        self._qr_lbl = QLabel()
        self._qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_lay.addWidget(self._qr_lbl)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        hint = QLabel("Share link or scan QR")
        hint.setObjectName("qrHint")
        hint.setWordWrap(True)

        self._speed_badge = StatBadge("↑", "— MB/s", color="#6c63ff")
        self._sent_badge  = StatBadge("📤", "—", color="#22c6a5")
        self._speed_badge.setFixedHeight(30)
        self._sent_badge.setFixedHeight(30)

        self._stop_btn = QPushButton("Stop Sharing")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #1e1224; color: #e060a0; border: 1.5px solid #e060a070;"
            " border-radius: 12px; padding: 12px 28px; min-height: 44px; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background-color: #2a1530; border-color: #e060a0; color: #ff80c0; }"
            "QPushButton:pressed { background-color: #3a1840; }"
        )
        self._stop_btn.clicked.connect(self._stop_sharing)

        right_col.addWidget(hint)
        right_col.addWidget(self._speed_badge)
        right_col.addWidget(self._sent_badge)
        right_col.addStretch()
        right_col.addWidget(self._stop_btn)

        content_row.addWidget(qr_frame)
        content_row.addLayout(right_col, stretch=1)

        lay.addLayout(url_row)
        lay.addLayout(content_row)
        return card

    # ── Slots ──────────────────────────────────────────────────────────────

    def _on_files_chosen(self, paths: list):
        for p in paths:
            if p not in self._files:
                try:
                    # check if accessible
                    os.path.getsize(p)
                    self._files.append(p)
                    self._add_file_row(p)
                except Exception as e:
                    # File might be inaccessible, just skip it
                    pass
        if self._files:
            last_dir = os.path.dirname(self._files[-1])
            self._settings.setValue("sender/last_dir", last_dir)
            self._drop_zone.hide()
            self._file_list_card.show()
            self._action_btn.setEnabled(True)
            self._action_btn.setText("⬆  Share Files" if len(self._files) > 1 else "⬆  Share File")

    def _browse_files(self):
        last_dir = self._settings.value("sender/last_dir", os.path.expanduser("~"))
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files to share", last_dir)
        if paths:
            self._on_files_chosen(paths)

    def _add_more_files(self):
        last_dir = self._settings.value("sender/last_dir", os.path.expanduser("~"))
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files to share", last_dir)
        if paths:
            self._on_files_chosen(paths)

    def _toggle_sharing(self):
        if self._sharing:
            self._stop_sharing()
        else:
            self._start_sharing()

    def _start_sharing(self):
        self._sharing = True
        self._action_btn.hide()
        self._status_lbl.setText("")

        file_server.set_files(self._files)
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
        self._action_btn.show()
        self._action_btn.setEnabled(bool(self._files))
        self._action_btn.setText("⬆  Share Files" if len(self._files) > 1 else "⬆  Share File")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setText("")

    def _on_tunnel_url(self, url: str):
        self._loading_card.stop()
        self._loading_card.hide()

        self._url_edit.setText(url)
        px = _make_qr_pixmap(url, size=136)
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
        self._action_btn.setEnabled(bool(self._files))
        self._action_btn.setText("⬆  Share Files" if len(self._files) > 1 else "⬆  Share File")
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
