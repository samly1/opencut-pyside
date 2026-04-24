from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem

from app.domain.clips.base_clip import BaseClip


class ClipItem(QGraphicsRectItem):
    def __init__(self, clip: BaseClip, rect: QRectF, color_hex: str, is_selected: bool = False) -> None:
        super().__init__(QRectF(0.0, 0.0, rect.width(), rect.height()))
        self.clip = clip
        self._base_color_hex = color_hex
        self.setPos(rect.x(), rect.y())
        self._label = QGraphicsSimpleTextItem(clip.name, self)
        self._label.setBrush(QBrush(QColor("#0b1620")))
        self._label.setPos(8.0, 6.0)
        self._label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.set_selected_state(is_selected)

    def hit_test_edge(self, scene_x: float, handle_width: float = 8.0) -> str | None:
        local_x = scene_x - self.scenePos().x()
        clip_width = self.rect().width()
        if clip_width <= 0:
            return None
        if 0.0 <= local_x <= handle_width:
            return "left"
        if clip_width - handle_width <= local_x <= clip_width:
            return "right"
        return None

    def set_display_geometry(self, scene_x: float, width: float) -> None:
        clamped_width = max(1.0, width)
        self.setPos(scene_x, self.scenePos().y())
        self.setRect(QRectF(0.0, 0.0, clamped_width, self.rect().height()))

    def set_selected_state(self, is_selected: bool) -> None:
        if is_selected:
            self.setPen(QPen(QColor("#ff5a36"), 2))
            self.setBrush(QBrush(QColor(self._base_color_hex).lighter(108)))
            self.setZValue(12)
            return

        self.setPen(QPen(QColor("#1f2933"), 1))
        self.setBrush(QBrush(QColor(self._base_color_hex)))
        self.setZValue(10)
