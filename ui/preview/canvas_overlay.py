from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget


class CanvasOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._text_lines: list[str] = []
        self._font_size = 14
        self._text_color = QColor(255, 255, 255, 220)
        self._background_color = QColor(0, 0, 0, 120)
        self._visible = False

    def set_overlay_text(self, lines: list[str]) -> None:
        self._text_lines = lines
        self._visible = bool(lines)
        self.update()

    def clear_overlay(self) -> None:
        self._text_lines = []
        self._visible = False
        self.update()

    def set_font_size(self, size: int) -> None:
        self._font_size = max(8, size)
        self.update()

    def paintEvent(self, event: object) -> None:
        if not self._visible or not self._text_lines:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Segoe UI", self._font_size)
        font.setBold(True)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        line_height = metrics.height() + 4
        total_height = line_height * len(self._text_lines) + 16
        max_width = max(metrics.horizontalAdvance(line) for line in self._text_lines) + 24

        bg_x = (self.width() - max_width) / 2.0
        bg_y = self.height() - total_height - 20.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background_color)
        painter.drawRoundedRect(QRectF(bg_x, bg_y, max_width, total_height), 6.0, 6.0)

        painter.setPen(self._text_color)
        text_y = bg_y + 8.0 + metrics.ascent()
        for line in self._text_lines:
            text_width = metrics.horizontalAdvance(line)
            text_x = bg_x + (max_width - text_width) / 2.0
            painter.drawText(int(text_x), int(text_y), line)
            text_y += line_height

        painter.end()
