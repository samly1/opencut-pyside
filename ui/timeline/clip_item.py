from __future__ import annotations

from app.domain.clips.base_clip import BaseClip
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsSimpleTextItem


class ClipItem(QGraphicsRectItem):
    def __init__(
        self,
        clip: BaseClip,
        rect: QRectF,
        color_hex: str,
        thumbnail: QPixmap | None = None,
        is_selected: bool = False,
    ) -> None:
        super().__init__(QRectF(0.0, 0.0, rect.width(), rect.height()))
        self.clip = clip
        self._base_color_hex = color_hex
        self._thumbnail_source = thumbnail
        self._thumbnail_item: QGraphicsPixmapItem | None = None
        self.setPos(rect.x(), rect.y())

        if thumbnail is not None and not thumbnail.isNull():
            self._thumbnail_item = QGraphicsPixmapItem(self)
            self._thumbnail_item.setOpacity(0.5)
            self._thumbnail_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._thumbnail_item.setZValue(1)
            self._refresh_thumbnail_pixmap()

        self._label = QGraphicsSimpleTextItem(clip.name, self)
        self._label.setBrush(QBrush(QColor("#0b1620")))
        self._label.setPos(8.0, 6.0)
        self._label.setZValue(2)
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
        self._refresh_thumbnail_pixmap()

    def set_selected_state(self, is_selected: bool) -> None:
        if is_selected:
            self.setPen(QPen(QColor("#ff5a36"), 2))
            self.setBrush(QBrush(QColor(self._base_color_hex).lighter(108)))
            self.setZValue(12)
            return

        self.setPen(QPen(QColor("#1f2933"), 1))
        self.setBrush(QBrush(QColor(self._base_color_hex)))
        self.setZValue(10)

    def _refresh_thumbnail_pixmap(self) -> None:
        if self._thumbnail_item is None or self._thumbnail_source is None:
            return

        width = max(1, int(self.rect().width()))
        height = max(1, int(self.rect().height()))
        scaled = self._thumbnail_source.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_item.setPixmap(scaled)
        self._thumbnail_item.setPos(0.0, 0.0)
