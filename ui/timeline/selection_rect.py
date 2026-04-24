from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsRectItem


class SelectionRect(QGraphicsRectItem):
    def __init__(self, origin: QPointF) -> None:
        super().__init__()
        self._origin = origin
        self.setRect(QRectF(origin, origin))
        self.setPen(QPen(QColor(70, 130, 200, 200), 1, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(70, 130, 200, 40)))
        self.setZValue(50)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    @property
    def origin(self) -> QPointF:
        return self._origin

    def update_to(self, current: QPointF) -> None:
        x = min(self._origin.x(), current.x())
        y = min(self._origin.y(), current.y())
        w = abs(current.x() - self._origin.x())
        h = abs(current.y() - self._origin.y())
        self.setRect(QRectF(x, y, w, h))

    def selected_rect(self) -> QRectF:
        return self.rect()
