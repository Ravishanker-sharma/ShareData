"""Custom-painted widgets: SpinnerWidget, AnimatedProgressBar, PillToggle."""

import math

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtProperty, QRect, QRectF, QPoint, pyqtSignal,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QLinearGradient, QFont, QFontMetrics,
)
from PyQt6.QtWidgets import QWidget, QSizePolicy


# ── Spinner ────────────────────────────────────────────────────────────────

class SpinnerWidget(QWidget):
    """Rotating dot-ring loading indicator."""

    def __init__(self, parent=None, size: int = 36, color: str = "#7c6ef7"):
        super().__init__(parent)
        self._color = QColor(color)
        self._angle = 0
        self._size = size
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self.show()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self._size / 2
        cy = self._size / 2
        radius = self._size / 2 - 4
        dot_r = self._size * 0.09
        n = 10
        for i in range(n):
            angle = math.radians(self._angle + i * (360 / n))
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            alpha = int(255 * (i + 1) / n * 0.95)
            c = QColor(self._color)
            c.setAlpha(alpha)
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x - dot_r, y - dot_r, dot_r * 2, dot_r * 2))
        p.end()


# ── Animated Progress Bar ──────────────────────────────────────────────────

class AnimatedProgressBar(QWidget):
    """Custom progress bar with gradient fill and shimmer animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0          # 0–100
        self._shimmer_x = 0.0   # 0.0–1.0 position of shimmer streak
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(16)
        self._shimmer_timer.timeout.connect(self._tick_shimmer)

    def setValue(self, v: int):
        self._value = max(0, min(100, v))
        if self._value > 0 and not self._shimmer_timer.isActive():
            self._shimmer_timer.start()
        if self._value == 0:
            self._shimmer_timer.stop()
        self.update()

    def value(self) -> int:
        return self._value

    def _tick_shimmer(self):
        self._shimmer_x = (self._shimmer_x + 0.008) % 1.2
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        r = h / 2

        # Background track
        p.setBrush(QBrush(QColor("#1a1a2a")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        if self._value <= 0:
            p.end()
            return

        fill_w = w * self._value / 100

        # Clip to fill area
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, fill_w, h), r, r)
        p.setClipPath(clip)

        # Gradient fill
        grad = QLinearGradient(0, 0, fill_w, 0)
        grad.setColorAt(0.0, QColor("#6c63ff"))
        grad.setColorAt(1.0, QColor("#22c6a5"))
        p.fillRect(QRectF(0, 0, fill_w, h), grad)

        # Shimmer streak
        sx = self._shimmer_x * fill_w
        shimmer = QLinearGradient(sx - 60, 0, sx + 60, 0)
        shimmer.setColorAt(0.0,  QColor(255, 255, 255, 0))
        shimmer.setColorAt(0.5,  QColor(255, 255, 255, 55))
        shimmer.setColorAt(1.0,  QColor(255, 255, 255, 0))
        p.fillRect(QRectF(sx - 60, 0, 120, h), shimmer)

        p.setClipping(False)
        p.end()


# ── Pill Toggle ────────────────────────────────────────────────────────────

class PillToggle(QWidget):
    """
    A two-option segmented toggle that slides a filled pill indicator.
    Emits `changed(index)` when selection changes.
    """

    changed = pyqtSignal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        assert len(labels) == 2
        self._labels = labels
        self._current = 0
        self._target = 0
        self._pill_x = 0.0        # animated 0.0 = left, 1.0 = right

        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(12)
        self._anim_timer.timeout.connect(self._animate)

    def setIndex(self, index: int):
        if index == self._current:
            return
        self._current = index
        self._target = float(index)
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def index(self) -> int:
        return self._current

    def _animate(self):
        target = float(self._target)
        diff = target - self._pill_x
        if abs(diff) < 0.01:
            self._pill_x = target
            self._anim_timer.stop()
        else:
            self._pill_x += diff * 0.22
        self.update()

    def mousePressEvent(self, event):
        mid = self.width() / 2
        idx = 0 if event.position().x() < mid else 1
        if idx != self._current:
            self._current = idx
            self._target = float(idx)
            if not self._anim_timer.isActive():
                self._anim_timer.start()
            self.changed.emit(idx)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        pad = 4
        half_w = (w - pad * 2) / 2
        r = (h - pad * 2) / 2

        # Outer track
        p.setBrush(QBrush(QColor("#12121e")))
        p.setPen(QPen(QColor("#ffffff12"), 1))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)

        # Sliding pill indicator
        pill_x = pad + self._pill_x * half_w
        grad = QLinearGradient(pill_x, 0, pill_x + half_w, 0)
        grad.setColorAt(0.0, QColor("#6c63ff"))
        grad.setColorAt(1.0, QColor("#8b5cf6"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(pill_x, pad, half_w, h - pad * 2), r, r)

        # Labels
        font = QFont()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)

        for i, label in enumerate(self._labels):
            lx = pad + i * half_w
            lr = QRectF(lx, pad, half_w, h - pad * 2)
            if i == self._current:
                p.setPen(QPen(QColor("#ffffff")))
            else:
                p.setPen(QPen(QColor("#5a5a8a")))
            p.drawText(lr, Qt.AlignmentFlag.AlignCenter, label)

        p.end()


# ── Stat Badge ─────────────────────────────────────────────────────────────

class StatBadge(QWidget):
    """A small pill-shaped stat chip with an icon and value."""

    def __init__(self, icon: str, value: str = "—", color: str = "#6c63ff", parent=None):
        super().__init__(parent)
        self._icon = icon
        self._value = value
        self._color = QColor(color)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setValue(self, value: str):
        self._value = value
        self.update()

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        fm = QFontMetrics(QFont())
        text_w = fm.horizontalAdvance(f"  {self._icon}  {self._value}  ")
        return QSize(max(text_w + 24, 100), 32)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        bg = QColor(self._color)
        bg.setAlpha(30)
        p.setBrush(QBrush(bg))
        border = QColor(self._color)
        border.setAlpha(80)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)

        font = QFont()
        font.setPointSize(11)
        p.setFont(font)
        p.setPen(QPen(self._color.lighter(150)))

        p.drawText(
            QRectF(0, 0, w, h),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._icon}  {self._value}",
        )
        p.end()
