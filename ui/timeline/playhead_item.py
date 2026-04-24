from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem


class PlayheadItem(QGraphicsLineItem):
    def __init__(self, x_position: float, bounds: QRectF) -> None:
        super().__init__(x_position, bounds.top(), x_position, bounds.bottom())
        self.setPen(QPen(QColor("#ff5a36"), 2))
        self.setZValue(20)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        top_y = bounds.top()
        marker = QGraphicsPolygonItem(
            QPolygonF(
                [
                    QPointF(x_position, top_y),
                    QPointF(x_position - 6, top_y + 10),
                    QPointF(x_position + 6, top_y + 10),
                ]
            ),
            self,
        )
        marker.setBrush(QBrush(QColor("#ff5a36")))
        marker.setPen(QPen(QColor("#ff5a36"), 1))
        marker.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
