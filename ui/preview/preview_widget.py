from __future__ import annotations

from app.controllers.playback_controller import PlaybackController
from app.ui.preview.playback_toolbar import PlaybackToolbar
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PreviewWidget(QWidget):
    def __init__(self, playback_controller: PlaybackController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._playback_controller = playback_controller

        layout = QVBoxLayout(self)
        self.preview_canvas = QLabel("No frame", self)
        self.preview_canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_canvas.setMinimumHeight(240)
        self.preview_canvas.setObjectName("preview_canvas")
        self.preview_canvas.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        self._playback_controller.current_time_changed.connect(self._on_current_time_changed)
        self._playback_controller.preview_frame_changed.connect(self._on_preview_frame_changed)
        self._playback_controller.preview_message_changed.connect(self._on_preview_message_changed)
        self._playback_controller.playback_state_changed.connect(self._on_playback_state_changed)

        self._current_time = self._playback_controller.current_time()
        self._current_preview_image: QImage | None = self._playback_controller.latest_preview_image()
        self._preview_message = self._playback_controller.latest_preview_message()
        self._is_playing = self._playback_controller.is_playing()

        layout.addWidget(self.preview_canvas, 1)
        layout.addWidget(PlaybackToolbar(self._playback_controller, self))
        self._render_preview()

    def _on_current_time_changed(self, current_time: float) -> None:
        self._current_time = current_time
        if self._current_preview_image is None:
            self._render_preview()

    def _on_preview_frame_changed(self, frame_image: object) -> None:
        if isinstance(frame_image, QImage) and not frame_image.isNull():
            self._current_preview_image = frame_image
        else:
            self._current_preview_image = None
        self._render_preview()

    def _on_preview_message_changed(self, message: str) -> None:
        self._preview_message = message
        if self._current_preview_image is None:
            self._render_preview()

    def _on_playback_state_changed(self, state: str) -> None:
        self._is_playing = state == "playing"
        if self._current_preview_image is not None:
            self._render_preview()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._current_preview_image is not None:
            self._render_preview()

    def _render_preview(self) -> None:
        if self._current_preview_image is None:
            self.preview_canvas.setPixmap(QPixmap())
            self.preview_canvas.setText(f"{self._preview_message}\nTime: {self._current_time:0.2f}s")
            return

        pixmap = QPixmap.fromImage(self._current_preview_image)
        target_size = self.preview_canvas.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            self.preview_canvas.setPixmap(pixmap)
            self.preview_canvas.setText("")
            return

        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation if self._is_playing else Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_canvas.setPixmap(scaled)
        self.preview_canvas.setText("")
