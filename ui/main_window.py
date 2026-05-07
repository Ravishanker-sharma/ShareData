from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.sender_panel import SenderPanel
from ui.receiver_panel import ReceiverPanel
from ui.widgets import PillToggle
from ui.styles import APP_STYLE


class LogoWidget(QWidget):
    """Small geometric logo mark drawn with QPainter."""

    def __init__(self, size: int = 36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = h = self.width()
        pad = 4

        # Outer circle with gradient
        from PyQt6.QtCore import QRectF
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#6c63ff"))
        grad.setColorAt(1.0, QColor("#22c6a5"))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(pad, pad, w - pad * 2, h - pad * 2))

        # Inner arrow / share icon
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        cx, cy = w / 2, h / 2
        s = w * 0.22
        p.setBrush(QColor(255, 255, 255, 230))
        # Up-right arrow shape (simplified as a small triangle)
        tri = QPolygonF([
            QPointF(cx - s * 0.8, cy + s * 0.6),
            QPointF(cx + s * 0.9, cy - s * 0.6),
            QPointF(cx + s * 0.9, cy + s * 0.5),
        ])
        p.drawPolygon(tri)
        p.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ShareData")
        self.setMinimumSize(480, 620)
        self.resize(500, 720)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet("background-color: #0a0a14;")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(76)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 16, 24, 14)
        hl.setSpacing(12)

        logo = LogoWidget(size=34)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        t = QLabel("ShareData")
        t.setObjectName("appTitle")
        sub = QLabel("Peer-to-peer · No cloud · No limits")
        sub.setObjectName("appSubtitle")
        title_col.addWidget(t)
        title_col.addWidget(sub)

        hl.addWidget(logo)
        hl.addLayout(title_col)
        hl.addStretch()
        outer.addWidget(header)

        # ── Toggle ────────────────────────────────────────────
        toggle_wrapper = QWidget()
        toggle_wrapper.setStyleSheet("background-color: #0a0a14;")
        toggle_wrapper.setFixedHeight(62)
        tw = QHBoxLayout(toggle_wrapper)
        tw.setContentsMargins(24, 8, 24, 8)

        self._toggle = PillToggle(["  📤   Send  ", "  📥   Receive  "])
        self._toggle.changed.connect(self._switch)
        tw.addWidget(self._toggle)
        outer.addWidget(toggle_wrapper)

        # ── Separator ─────────────────────────────────────────
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #ffffff08;")
        outer.addWidget(sep)

        # ── Content ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_host = QWidget()
        content_host.setStyleSheet("background-color: #0a0a14;")
        cl = QVBoxLayout(content_host)
        cl.setContentsMargins(24, 20, 24, 28)
        cl.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        self._sender_panel = SenderPanel()
        self._receiver_panel = ReceiverPanel()
        self._stack.addWidget(self._sender_panel)
        self._stack.addWidget(self._receiver_panel)

        cl.addWidget(self._stack)
        scroll.setWidget(content_host)
        outer.addWidget(scroll, stretch=1)

    def _switch(self, index: int):
        self._stack.setCurrentIndex(index)
        self._toggle.setIndex(index)
